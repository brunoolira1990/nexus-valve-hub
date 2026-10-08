"""Créditos financeiros de cliente e fornecedor — ERP 4.0.14.1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro, forma_requer_conta_real, label_forma_pagamento
from apps.financeiro.models import (
    BaixaFinanceira,
    CreditoFinanceiro,
    CreditoFinanceiroEvento,
    FinanceiroEvento,
    ParcelaFinanceira,
    TituloFinanceiro,
)
from apps.financeiro.operacional import credito_motivo_bloqueio_exclusao
from apps.financeiro.services.eventos import registrar_evento_financeiro
from apps.financeiro.services.movimento import _resolver_parcela_saldo

CENTAVO = Decimal('0.01')


class CreditoFinanceiroError(ValueError):
    pass


def somar_uso_credito(credito: CreditoFinanceiro) -> Decimal:
    total = Decimal('0')
    for bx in credito.movimentos.filter(
        tipo_movimento=TipoMovimentoFinanceiro.USO_CREDITO,
        estornada=False,
    ):
        total += bx.valor
    for bx in credito.movimentos.filter(
        tipo_movimento__in=(
            TipoMovimentoFinanceiro.REEMBOLSO_CLIENTE,
            TipoMovimentoFinanceiro.REEMBOLSO_FORNECEDOR,
        ),
        estornada=False,
    ):
        total += bx.valor
    return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _registrar_evento_credito(
    credito: CreditoFinanceiro,
    *,
    acao: str,
    descricao: str,
    valor: Decimal | None = None,
    titulo_numero: str = '',
    baixa_id: int | None = None,
    usuario=None,
) -> None:
    CreditoFinanceiroEvento.objects.create(
        credito=credito,
        acao=acao,
        descricao=descricao,
        valor=valor,
        titulo_numero=titulo_numero,
        baixa_id=baixa_id,
        usuario=usuario,
    )


@transaction.atomic
def criar_credito_financeiro(
    *,
    tipo: str,
    cliente_id: int | None = None,
    fornecedor_id: int | None = None,
    valor_original: Decimal,
    data_credito: date,
    motivo: str,
    origem_tipo: str = CreditoFinanceiro.OrigemTipo.MANUAL,
    origem_descricao: str = '',
    origem_numero: str = '',
    observacoes: str = '',
    usuario=None,
) -> CreditoFinanceiro:
    motivo = (motivo or '').strip()
    if not motivo:
        raise CreditoFinanceiroError('Informe o motivo do crédito.')
    valor_original = valor_original.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if valor_original <= 0:
        raise CreditoFinanceiroError('O valor do crédito deve ser maior que zero.')
    if tipo == CreditoFinanceiro.Tipo.CLIENTE:
        if not cliente_id:
            raise CreditoFinanceiroError('Informe o cliente para crédito de cliente.')
        fornecedor_id = None
    elif tipo == CreditoFinanceiro.Tipo.FORNECEDOR:
        if not fornecedor_id:
            raise CreditoFinanceiroError('Informe o fornecedor para crédito de fornecedor.')
        cliente_id = None
    else:
        raise CreditoFinanceiroError('Tipo de crédito inválido.')

    credito = CreditoFinanceiro.objects.create(
        tipo=tipo,
        cliente_id=cliente_id,
        fornecedor_id=fornecedor_id,
        valor_original=valor_original,
        valor_utilizado=Decimal('0'),
        saldo=valor_original,
        status=CreditoFinanceiro.Status.DISPONIVEL,
        origem_tipo=origem_tipo,
        origem_descricao=(origem_descricao or '').strip(),
        origem_numero=(origem_numero or '').strip(),
        data_credito=data_credito,
        motivo=motivo,
        observacoes=(observacoes or '').strip(),
        criado_por=usuario,
    )
    tipo_label = 'cliente' if tipo == CreditoFinanceiro.Tipo.CLIENTE else 'fornecedor'
    _registrar_evento_credito(
        credito,
        acao=CreditoFinanceiroEvento.Acao.CRIACAO,
        descricao=f'Crédito de {tipo_label} criado no valor de R$ {valor_original:.2f}.',
        valor=valor_original,
        usuario=usuario,
    )
    return credito


def _validar_credito_titulo_compativel(credito: CreditoFinanceiro, titulo: TituloFinanceiro) -> None:
    if credito.cancelado or credito.status == CreditoFinanceiro.Status.CANCELADO:
        raise CreditoFinanceiroError('Crédito cancelado não pode ser aplicado.')
    if not credito.pode_aplicar:
        raise CreditoFinanceiroError('Crédito sem saldo disponível.')
    if titulo.cancelado:
        raise CreditoFinanceiroError('Título cancelado não aceita crédito.')
    if credito.tipo == CreditoFinanceiro.Tipo.CLIENTE:
        if titulo.tipo != TituloFinanceiro.Tipo.RECEBER:
            raise CreditoFinanceiroError('Crédito de cliente só pode ser aplicado em contas a receber.')
        if titulo.cliente_id != credito.cliente_id:
            raise CreditoFinanceiroError('O crédito pertence a outro cliente.')
    else:
        if titulo.tipo != TituloFinanceiro.Tipo.PAGAR:
            raise CreditoFinanceiroError('Crédito de fornecedor só pode ser aplicado em contas a pagar.')
        if titulo.fornecedor_id != credito.fornecedor_id:
            raise CreditoFinanceiroError('O crédito pertence a outro fornecedor.')


@transaction.atomic
def aplicar_credito_em_titulo(
    credito: CreditoFinanceiro,
    titulo: TituloFinanceiro,
    *,
    valor: Decimal,
    data_aplicacao: date,
    parcela_id: int | None = None,
    motivo: str = '',
    observacoes: str = '',
    usuario=None,
) -> BaixaFinanceira:
    motivo = (motivo or observacoes or '').strip()
    if not motivo:
        raise CreditoFinanceiroError('Informe o motivo ou uma observação para aplicar o crédito.')
    _validar_credito_titulo_compativel(credito, titulo)
    if not titulo.pode_baixar:
        raise CreditoFinanceiroError('Não há saldo em aberto no título.')

    valor = valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if valor <= 0:
        raise CreditoFinanceiroError('Informe um valor maior que zero.')
    if valor > credito.saldo + CENTAVO:
        raise CreditoFinanceiroError('O valor excede o saldo do crédito.')

    parcela, saldo_titulo = _resolver_parcela_saldo(titulo, parcela_id)
    if valor > saldo_titulo + CENTAVO:
        raise CreditoFinanceiroError('O valor excede o saldo em aberto do título.')

    baixa = BaixaFinanceira.objects.create(
        titulo=titulo,
        parcela=parcela,
        credito=credito,
        tipo_movimento=TipoMovimentoFinanceiro.USO_CREDITO,
        forma_pagamento_codigo=FormaPagamentoCodigo.SEM_MOVIMENTACAO_FINANCEIRA,
        data_baixa=data_aplicacao,
        valor=valor,
        conta_financeira=None,
        observacoes=motivo,
        registrada_por=usuario,
    )
    if parcela:
        parcela.recalcular_saldos_e_status()
    titulo.recalcular_saldos_e_status()
    credito.recalcular_saldo_e_status()

    parcela_ref = f', parcela {parcela.numero_parcela:03d}' if parcela else ''
    desc_credito = f'Crédito aplicado no título {titulo.numero}{parcela_ref} no valor de R$ {valor:.2f}.'
    _registrar_evento_credito(
        credito,
        acao=CreditoFinanceiroEvento.Acao.APLICACAO,
        descricao=desc_credito,
        valor=valor,
        titulo_numero=titulo.numero,
        baixa_id=baixa.pk,
        usuario=usuario,
    )
    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.USO_CREDITO,
        descricao=f'Crédito aplicado no valor de R$ {valor:.2f}. {motivo}',
        usuario=usuario,
        dados_novos={'baixa_id': baixa.pk, 'credito_id': credito.pk, 'valor': str(valor)},
    )
    return baixa


@transaction.atomic
def cancelar_credito_financeiro(
    credito: CreditoFinanceiro,
    *,
    motivo: str,
    usuario=None,
) -> CreditoFinanceiro:
    if credito.cancelado:
        raise CreditoFinanceiroError('Este crédito já está cancelado.')
    if credito.valor_utilizado > CENTAVO:
        raise CreditoFinanceiroError(
            'Este crédito já possui utilização. Estorne os usos antes de cancelar o crédito integralmente.',
        )
    motivo = (motivo or '').strip()
    if not motivo:
        raise CreditoFinanceiroError('Informe o motivo do cancelamento.')
    credito.cancelado = True
    credito.motivo_cancelamento = motivo
    credito.cancelado_em = timezone.now()
    credito.status = CreditoFinanceiro.Status.CANCELADO
    credito.saldo = Decimal('0')
    credito.save(
        update_fields=[
            'cancelado',
            'motivo_cancelamento',
            'cancelado_em',
            'status',
            'saldo',
            'atualizado_em',
        ],
    )
    _registrar_evento_credito(
        credito,
        acao=CreditoFinanceiroEvento.Acao.CANCELAMENTO,
        descricao=f'Crédito cancelado. Motivo: {motivo}',
        usuario=usuario,
    )
    return credito


MSG_CREDITO_MOVIMENTO_BLOQUEIO = (
    'Este crédito já possui movimentações. Para manter o histórico, apenas observações '
    'e informações complementares podem ser editadas.'
)
MSG_CREDITO_EXCLUIR_BLOQUEIO = (
    'Este crédito possui movimentações ativas ou vínculo de origem e não pode ser excluído. '
    'Cancele ou estorne os movimentos para manter o histórico.'
)


@transaction.atomic
def atualizar_credito_financeiro(
    credito: CreditoFinanceiro,
    *,
    usuario=None,
    cliente_id: int | None = None,
    fornecedor_id: int | None = None,
    valor_original: Decimal | None = None,
    origem_tipo: str | None = None,
    origem_numero: str | None = None,
    origem_descricao: str | None = None,
    data_credito: date | None = None,
    motivo: str | None = None,
    observacoes: str | None = None,
) -> CreditoFinanceiro:
    from apps.financeiro.operacional import credito_operational_flags

    if credito.cancelado:
        raise CreditoFinanceiroError('Crédito cancelado não pode ser editado.')

    flags = credito_operational_flags(credito)
    pode_completo = flags['pode_editar_completo']
    alteracoes: list[str] = []
    update_fields: list[str] = []

    def _bloqueado(campo_alterado: bool) -> None:
        if campo_alterado and not pode_completo:
            raise CreditoFinanceiroError(MSG_CREDITO_MOVIMENTO_BLOQUEIO)

    if cliente_id is not None:
        _bloqueado(cliente_id != credito.cliente_id)
        if credito.tipo != CreditoFinanceiro.Tipo.CLIENTE:
            raise CreditoFinanceiroError('Informe o cliente apenas para crédito de cliente.')
        if not cliente_id:
            raise CreditoFinanceiroError('Informe o cliente para crédito de cliente.')
        if cliente_id != credito.cliente_id:
            credito.cliente_id = cliente_id
            update_fields.append('cliente_id')
            alteracoes.append('cliente')

    if fornecedor_id is not None:
        _bloqueado(fornecedor_id != credito.fornecedor_id)
        if credito.tipo != CreditoFinanceiro.Tipo.FORNECEDOR:
            raise CreditoFinanceiroError('Informe o fornecedor apenas para crédito de fornecedor.')
        if not fornecedor_id:
            raise CreditoFinanceiroError('Informe o fornecedor para crédito de fornecedor.')
        if fornecedor_id != credito.fornecedor_id:
            credito.fornecedor_id = fornecedor_id
            update_fields.append('fornecedor_id')
            alteracoes.append('fornecedor')

    if valor_original is not None:
        valor_original = valor_original.quantize(CENTAVO, rounding=ROUND_HALF_UP)
        _bloqueado(valor_original != credito.valor_original)
        if valor_original <= 0:
            raise CreditoFinanceiroError('O valor do crédito deve ser maior que zero.')
        if valor_original != credito.valor_original:
            credito.valor_original = valor_original
            update_fields.extend(['valor_original', 'saldo'])
            alteracoes.append('valor')

    if origem_tipo is not None:
        _bloqueado(origem_tipo != credito.origem_tipo)
        if origem_tipo != credito.origem_tipo:
            credito.origem_tipo = origem_tipo
            update_fields.append('origem_tipo')
            alteracoes.append('origem')

    if origem_numero is not None:
        novo = (origem_numero or '').strip()
        if novo != (credito.origem_numero or '').strip():
            credito.origem_numero = novo
            update_fields.append('origem_numero')
            alteracoes.append('documento')

    if origem_descricao is not None:
        nova = (origem_descricao or '').strip()
        if nova != (credito.origem_descricao or '').strip():
            credito.origem_descricao = nova
            update_fields.append('origem_descricao')
            alteracoes.append('origem_descricao')

    if data_credito is not None:
        _bloqueado(data_credito != credito.data_credito)
        if data_credito != credito.data_credito:
            credito.data_credito = data_credito
            update_fields.append('data_credito')
            alteracoes.append('data')

    if motivo is not None:
        novo_motivo = (motivo or '').strip()
        if pode_completo and not novo_motivo:
            raise CreditoFinanceiroError('Informe o motivo do crédito.')
        if novo_motivo != (credito.motivo or '').strip():
            credito.motivo = novo_motivo
            update_fields.append('motivo')
            alteracoes.append('motivo')

    if observacoes is not None:
        nova_obs = (observacoes or '').strip()
        if nova_obs != (credito.observacoes or '').strip():
            credito.observacoes = nova_obs
            update_fields.append('observacoes')
            alteracoes.append('observações')

    if not update_fields:
        return credito

    if 'valor_original' in update_fields:
        credito.recalcular_saldo_e_status(save=False)

    update_fields.append('atualizado_em')
    credito.save(update_fields=list(dict.fromkeys(update_fields)))

    campos_txt = ', '.join(sorted(set(alteracoes)))
    _registrar_evento_credito(
        credito,
        acao=CreditoFinanceiroEvento.Acao.EDICAO,
        descricao=f'Crédito editado ({campos_txt}).',
        usuario=usuario,
    )
    return credito


@transaction.atomic
def excluir_credito_financeiro(
    credito: CreditoFinanceiro,
    *,
    motivo: str,
    usuario=None,
) -> None:
    motivo = (motivo or '').strip()
    if not motivo:
        raise CreditoFinanceiroError('Informe o motivo da exclusão.')
    bloqueio = credito_motivo_bloqueio_exclusao(credito)
    if bloqueio:
        raise CreditoFinanceiroError(bloqueio)
    credito.movimentos.all().delete()
    credito.eventos.all().delete()
    credito.delete()


@transaction.atomic
def reembolsar_credito(
    credito: CreditoFinanceiro,
    *,
    valor: Decimal,
    data_reembolso: date,
    conta_financeira_id: int,
    forma_pagamento_codigo: str,
    observacoes: str = '',
    usuario=None,
) -> BaixaFinanceira:
    if credito.cancelado:
        raise CreditoFinanceiroError('Crédito cancelado não pode ser reembolsado.')
    if not forma_requer_conta_real(forma_pagamento_codigo):
        raise CreditoFinanceiroError('Informe uma forma de pagamento com movimentação financeira real.')
    valor = valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if valor <= 0:
        raise CreditoFinanceiroError('Informe um valor maior que zero.')
    if valor > credito.saldo + CENTAVO:
        raise CreditoFinanceiroError('O valor excede o saldo do crédito.')
    obs = (observacoes or '').strip()
    if not obs:
        raise CreditoFinanceiroError('Informe uma observação para o reembolso.')

    tipo_mov = (
        TipoMovimentoFinanceiro.REEMBOLSO_CLIENTE
        if credito.tipo == CreditoFinanceiro.Tipo.CLIENTE
        else TipoMovimentoFinanceiro.REEMBOLSO_FORNECEDOR
    )
    baixa = BaixaFinanceira.objects.create(
        titulo=None,
        credito=credito,
        tipo_movimento=tipo_mov,
        forma_pagamento_codigo=forma_pagamento_codigo,
        data_baixa=data_reembolso,
        valor=valor,
        conta_financeira_id=conta_financeira_id,
        observacoes=obs,
        registrada_por=usuario,
    )
    credito.recalcular_saldo_e_status()
    label = label_forma_pagamento(forma_pagamento_codigo)
    _registrar_evento_credito(
        credito,
        acao=CreditoFinanceiroEvento.Acao.REEMBOLSO,
        descricao=f'Reembolso de R$ {valor:.2f} via {label}. {obs}',
        valor=valor,
        baixa_id=baixa.pk,
        usuario=usuario,
    )
    return baixa


@transaction.atomic
def estornar_uso_credito(
    baixa: BaixaFinanceira,
    *,
    motivo: str,
    usuario=None,
) -> BaixaFinanceira:
    from apps.financeiro.services.baixa import estornar_baixa_financeira

    if baixa.tipo_movimento != TipoMovimentoFinanceiro.USO_CREDITO:
        raise CreditoFinanceiroError('Esta baixa não é um uso de crédito.')
    if baixa.estornada:
        raise CreditoFinanceiroError('Este movimento já foi estornado.')
    motivo = (motivo or '').strip()
    if not motivo:
        raise CreditoFinanceiroError('Informe o motivo do estorno.')

    baixa.estornada = True
    baixa.motivo_estorno = motivo
    baixa.estornada_em = timezone.now()
    baixa.estornada_por = usuario
    baixa.save(
        update_fields=['estornada', 'motivo_estorno', 'estornada_em', 'estornada_por'],
    )

    titulo = baixa.titulo
    parcela = baixa.parcela
    if parcela:
        parcela.recalcular_saldos_e_status()
    titulo.recalcular_saldos_e_status()

    credito = baixa.credito
    if credito:
        credito.recalcular_saldo_e_status()
        _registrar_evento_credito(
            credito,
            acao=CreditoFinanceiroEvento.Acao.ESTORNO_APLICACAO,
            descricao=f'Uso de crédito estornado. Saldo do crédito reaberto. Motivo: {motivo}',
            valor=baixa.valor,
            titulo_numero=titulo.numero,
            baixa_id=baixa.pk,
            usuario=usuario,
        )

    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.ESTORNO,
        descricao=f'Uso de crédito estornado. Saldo do título reaberto. Motivo: {motivo}',
        usuario=usuario,
        dados_anteriores={'baixa_id': baixa.pk, 'credito_id': credito.pk if credito else None},
    )
    return baixa
