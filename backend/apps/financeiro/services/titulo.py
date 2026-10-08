"""Serviços de títulos financeiros."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.financeiro.models import FinanceiroEvento, ParcelaFinanceira, TituloFinanceiro
from apps.financeiro.operacional import titulo_motivo_bloqueio_exclusao
from apps.financeiro.services.eventos import registrar_evento_financeiro

CENTAVO = Decimal('0.01')
TOLERANCIA_PARCELAS = Decimal('0.05')


def somar_baixas_titulo(titulo: TituloFinanceiro) -> Decimal:
    total = Decimal('0')
    for bx in titulo.baixas.filter(estornada=False):
        total += bx.valor
    return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def gerar_numero_titulo_financeiro(tipo: str, data_referencia: date | None = None) -> str:
    """Gera número CR-AAAA-000001 / CP-AAAA-000001 de forma transacional — ERP 4.0.14.8."""
    prefix = 'CR' if tipo == TituloFinanceiro.Tipo.RECEBER else 'CP'
    ref = data_referencia or timezone.localdate()
    ano = ref.year if hasattr(ref, 'year') else timezone.localdate().year
    base = f'{prefix}-{ano}-'

    with transaction.atomic():
        list(
            TituloFinanceiro.objects.filter(tipo=tipo, numero__startswith=base)
            .select_for_update()
            .order_by('-numero')
            .values_list('id', flat=True)[:1],
        )
        ultimo = (
            TituloFinanceiro.objects.filter(tipo=tipo, numero__startswith=base)
            .order_by('-numero')
            .values_list('numero', flat=True)
            .first()
        )
        seq = 1
        if ultimo:
            try:
                seq = int(ultimo.split('-')[-1]) + 1
            except ValueError:
                seq = TituloFinanceiro.objects.filter(tipo=tipo, numero__startswith=base).count() + 1
        numero = f'{base}{seq:06d}'
        while TituloFinanceiro.objects.filter(numero=numero).exists():
            seq += 1
            numero = f'{base}{seq:06d}'
        return numero


def proximo_numero_titulo(tipo: str, data_referencia: date | None = None) -> str:
    return gerar_numero_titulo_financeiro(tipo, data_referencia)


def montar_origem_descricao(origem_tipo: str, origem_numero: str = '', origem_descricao: str = '') -> str:
    if origem_descricao:
        return origem_descricao
    labels = dict(TituloFinanceiro.OrigemTipo.choices)
    base = labels.get(origem_tipo, origem_tipo)
    if origem_numero:
        return f'{base} {origem_numero}'
    return base


def gerar_parcelas_custom(
    titulo: TituloFinanceiro,
    parcelas_spec: list[dict],
) -> list[ParcelaFinanceira]:
    """Parcelas com vencimento e valor definidos (ex.: tributo parcelado)."""
    if not parcelas_spec:
        raise ValueError('Informe ao menos uma parcela.')
    parcelas: list[ParcelaFinanceira] = []
    for i, spec in enumerate(parcelas_spec, start=1):
        venc = spec.get('data_vencimento') or spec.get('vencimento')
        val = Decimal(str(spec['valor'])).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        num = int(spec.get('numero_parcela') or i)
        p = ParcelaFinanceira.objects.create(
            titulo=titulo,
            numero_parcela=num,
            data_vencimento=venc,
            valor_original=val,
            valor_aberto=val,
            valor_baixado=Decimal('0'),
            status=TituloFinanceiro.Status.EM_ABERTO,
            observacoes=(spec.get('observacoes') or '')[:500],
        )
        parcelas.append(p)
    err = validar_soma_parcelas(titulo)
    if err:
        raise ValueError(err)
    return parcelas


def gerar_parcelas_condicao(
    titulo: TituloFinanceiro,
    *,
    quantidade: int,
    intervalo_dias: int,
    primeiro_vencimento_dias: int,
) -> list[ParcelaFinanceira]:
    if quantidade < 1:
        quantidade = 1
    valor_parcela = (titulo.valor_original / quantidade).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    parcelas: list[ParcelaFinanceira] = []
    venc = titulo.data_emissao + timedelta(days=primeiro_vencimento_dias)
    soma = Decimal('0')
    for i in range(1, quantidade + 1):
        if i == quantidade:
            val = titulo.valor_original - soma
        else:
            val = valor_parcela
            soma += val
        p = ParcelaFinanceira.objects.create(
            titulo=titulo,
            numero_parcela=i,
            data_vencimento=venc,
            valor_original=val,
            valor_aberto=val,
            valor_baixado=Decimal('0'),
            status=TituloFinanceiro.Status.EM_ABERTO,
        )
        parcelas.append(p)
        venc = venc + timedelta(days=intervalo_dias)
    return parcelas


def validar_soma_parcelas(titulo: TituloFinanceiro) -> str | None:
    parcelas = list(titulo.parcelas.all())
    if not parcelas:
        return None
    soma = sum(p.valor_original for p in parcelas)
    diff = abs(soma - titulo.valor_original)
    if diff > TOLERANCIA_PARCELAS:
        return (
            f'A soma das parcelas (R$ {soma}) diverge do valor do título (R$ {titulo.valor_original}).'
        )
    return None


def validar_titulo_pagar(
    *,
    tipo_lancamento: str,
    fornecedor_id: int | None,
    descricao: str,
    tipo_tributo: str,
    competencia: date | None,
) -> None:
    lanc = tipo_lancamento or TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR
    if lanc == TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR and not fornecedor_id:
        raise ValueError('Informe o fornecedor para este lançamento.')
    if lanc in (
        TituloFinanceiro.TipoLancamentoPagar.DESPESA_OPERACIONAL,
        TituloFinanceiro.TipoLancamentoPagar.OUTROS,
    ) and not (descricao or '').strip():
        raise ValueError('Informe a descrição da despesa.')
    if lanc == TituloFinanceiro.TipoLancamentoPagar.TRIBUTO_IMPOSTO:
        if not tipo_tributo:
            raise ValueError('Informe o tipo de tributo.')
        if not competencia:
            raise ValueError('Informe a competência do tributo.')
    if lanc == TituloFinanceiro.TipoLancamentoPagar.SERVICO and not (
        (descricao or '').strip() or fornecedor_id
    ):
        raise ValueError('Informe a descrição ou o fornecedor do serviço.')


@transaction.atomic
def criar_titulo_financeiro(
    *,
    tipo: str,
    numero: str | None = None,
    cliente_id: int | None = None,
    fornecedor_id: int | None = None,
    tipo_lancamento: str = '',
    descricao: str = '',
    competencia: date | None = None,
    tipo_tributo: str = '',
    periodo_apuracao: str = '',
    numero_guia: str = '',
    codigo_receita: str = '',
    data_emissao: date,
    data_vencimento: date,
    valor_original: Decimal,
    origem_tipo: str = TituloFinanceiro.OrigemTipo.MANUAL,
    origem_id: int | None = None,
    origem_numero: str = '',
    origem_descricao: str = '',
    origem_data: date | None = None,
    documento_origem: str = '',
    forma_pagamento_prevista_codigo: str = '',
    conta_financeira_prevista_id: int | None = None,
    categoria_id: int | None = None,
    centro_custo_id: int | None = None,
    observacoes: str = '',
    gerar_parcelas: bool = False,
    quantidade_parcelas: int = 1,
    intervalo_dias: int = 30,
    primeiro_vencimento_dias: int = 0,
    parcelas_custom: list[dict] | None = None,
    usuario=None,
) -> TituloFinanceiro:
    if valor_original <= 0:
        raise ValueError('O valor do título deve ser maior que zero.')
    if tipo == TituloFinanceiro.Tipo.RECEBER and not cliente_id:
        raise ValueError('Informe o cliente para contas a receber.')
    if tipo == TituloFinanceiro.Tipo.PAGAR:
        if not tipo_lancamento:
            if tipo_tributo:
                tipo_lancamento = TituloFinanceiro.TipoLancamentoPagar.TRIBUTO_IMPOSTO
            elif fornecedor_id:
                tipo_lancamento = TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR
            else:
                tipo_lancamento = TituloFinanceiro.TipoLancamentoPagar.DESPESA_OPERACIONAL
        lanc_pagar = tipo_lancamento
        validar_titulo_pagar(
            tipo_lancamento=lanc_pagar,
            fornecedor_id=fornecedor_id,
            descricao=descricao,
            tipo_tributo=tipo_tributo,
            competencia=competencia,
        )
    if not data_vencimento:
        raise ValueError('Informe a data de vencimento.')

    numero = (numero or '').strip() or gerar_numero_titulo_financeiro(tipo, data_emissao)
    desc = montar_origem_descricao(origem_tipo, origem_numero, origem_descricao)
    if tipo == TituloFinanceiro.Tipo.PAGAR and tipo_lancamento == TituloFinanceiro.TipoLancamentoPagar.TRIBUTO_IMPOSTO:
        trib_label = dict(TituloFinanceiro.TipoTributo.choices).get(tipo_tributo, tipo_tributo)
        comp = competencia.strftime('%m/%Y') if competencia else ''
        desc = f'Tributo {trib_label}' + (f' — competência {comp}' if comp else '')
        if periodo_apuracao:
            desc += f' ({periodo_apuracao})'

    titulo = TituloFinanceiro.objects.create(
        tipo=tipo,
        numero=numero,
        cliente_id=cliente_id,
        fornecedor_id=fornecedor_id,
        tipo_lancamento=tipo_lancamento or '',
        descricao=(descricao or '').strip(),
        competencia=competencia,
        tipo_tributo=tipo_tributo or '',
        periodo_apuracao=(periodo_apuracao or '').strip(),
        numero_guia=(numero_guia or '').strip(),
        codigo_receita=(codigo_receita or '').strip(),
        documento_origem=documento_origem or '',
        origem_tipo=origem_tipo,
        origem_id=origem_id,
        origem_descricao=desc,
        origem_numero=origem_numero or '',
        origem_data=origem_data,
        data_emissao=data_emissao,
        data_vencimento=data_vencimento,
        valor_original=valor_original.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        valor_aberto=valor_original.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        valor_baixado=Decimal('0'),
        forma_pagamento_prevista_codigo=(forma_pagamento_prevista_codigo or '').strip(),
        conta_financeira_prevista_id=conta_financeira_prevista_id,
        categoria_id=categoria_id,
        centro_custo_id=centro_custo_id,
        observacoes=observacoes or '',
        criado_por=usuario,
    )
    titulo.recalcular_saldos_e_status()

    if parcelas_custom:
        parcelas = gerar_parcelas_custom(titulo, parcelas_custom)
        msg_parcelas = f' com {len(parcelas)} parcelas'
    elif gerar_parcelas and quantidade_parcelas > 1:
        gerar_parcelas_condicao(
            titulo,
            quantidade=quantidade_parcelas,
            intervalo_dias=intervalo_dias,
            primeiro_vencimento_dias=primeiro_vencimento_dias,
        )
        msg_parcelas = f' com {quantidade_parcelas} parcelas'
    else:
        ParcelaFinanceira.objects.create(
            titulo=titulo,
            numero_parcela=1,
            data_vencimento=data_vencimento,
            valor_original=titulo.valor_original,
            valor_aberto=titulo.valor_original,
            valor_baixado=Decimal('0'),
            status=titulo.status,
        )
        msg_parcelas = ''

    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.CRIACAO,
        descricao=f'Título {numero} criado{msg_parcelas}.',
        usuario=usuario,
        dados_novos={'valor_original': str(titulo.valor_original), 'vencimento': str(data_vencimento)},
    )
    return titulo


@transaction.atomic
def cancelar_titulo_financeiro(titulo: TituloFinanceiro, *, motivo: str, usuario=None) -> TituloFinanceiro:
    if titulo.cancelado:
        raise ValueError('Este título já está cancelado.')
    if titulo.valor_baixado > CENTAVO:
        raise ValueError('Estorne as baixas antes de cancelar o título.')
    titulo.cancelado = True
    titulo.motivo_cancelamento = (motivo or '').strip()
    titulo.cancelado_em = timezone.now()
    titulo.save(update_fields=['cancelado', 'motivo_cancelamento', 'cancelado_em', 'atualizado_em'])
    titulo.recalcular_saldos_e_status()
    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.CANCELAMENTO,
        descricao=f'Título cancelado. Motivo: {titulo.motivo_cancelamento}',
        usuario=usuario,
    )
    return titulo


MSG_TITULO_EXCLUIR_BLOQUEIO = (
    'Este título possui movimentações ativas ou vínculo de origem e não pode ser excluído. '
    'Cancele ou estorne os movimentos para manter o histórico.'
)


@transaction.atomic
def excluir_titulo_financeiro(titulo: TituloFinanceiro, *, motivo: str, usuario=None) -> None:
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValueError('Informe o motivo da exclusão.')
    bloqueio = titulo_motivo_bloqueio_exclusao(titulo)
    if bloqueio:
        raise ValueError(bloqueio)
    titulo.baixas.all().delete()
    titulo.eventos.all().delete()
    titulo.parcelas.all().delete()
    titulo.delete()
