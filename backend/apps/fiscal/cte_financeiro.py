"""CT-e importado — rateio de frete e geração explícita de Contas a Pagar (+ impostos).

Escopo V1:
- Rateio assistido proporcional ao valor das NF-es referenciadas (editável).
- CP do frete para a transportadora (resolvida como Fornecedor por CNPJ).
- Opcional: títulos tributo separados (ICMS / CBS / IBS) quando valor > 0.
- Sem estoque, expedição ou alteração automática de custo de produto.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.cadastros.models import Fornecedor
from apps.financeiro.models import CategoriaFinanceira, ContaFinanceira, CentroCusto, TituloFinanceiro
from apps.financeiro.services.titulo import criar_titulo_financeiro
from apps.fiscal.cte_historico_conferencia import resolver_documentos_vinculados
from apps.fiscal.models import CTeHistoricoImportado, NFeEntradaHistoricaImportada, NFeSaidaHistoricaImportada
from apps.fiscal.serializers import resumo_impostos_cte_operacional
from apps.produtos.cnpj_fornecedor import cnpj_apenas_digitos

CENTAVO = Decimal('0.01')

MSG_NAO_CONFERIDO = 'CT-e precisa estar conferido e apto operacionalmente para rateio/financeiro.'
MSG_CANCELADO = 'CT-e cancelado não pode gerar rateio nem contas a pagar.'
MSG_HOMOLOG = 'CT-e de homologação não gera financeiro operacional.'
MSG_SEM_CREDOR = (
    'Transportadora/emitente sem fornecedor cadastrado pelo CNPJ. '
    'Cadastre o fornecedor da transportadora antes de gerar o CP.'
)
MSG_VALOR_ZERO = 'Valor do frete inválido para gerar contas a pagar.'
MSG_JA_GERADO = 'Contas a pagar já foram geradas para este CT-e.'
MSG_TITULO_CANCELADO = (
    'Já existe título financeiro vinculado a este CT-e (inclusive cancelado). Revise antes de gerar novamente.'
)
MSG_RATEIO_SOMA = 'A soma do rateio não confere com o valor-base do frete.'
MSG_RATEIO_VAZIO = 'Informe ao menos uma linha de rateio.'
MSG_SEM_NFE = 'Nenhuma NF-e referenciada no XML para ratear o frete.'


class CteFinanceiroErro(ValueError):
    pass


def _round_money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def valor_base_frete_cte(cte: CTeHistoricoImportado) -> Decimal:
    receber = _round_money(cte.valor_receber or 0)
    if receber > 0:
        return receber
    return _round_money(cte.valor_total_servico or 0)


def _cte_apto_financeiro(cte: CTeHistoricoImportado) -> None:
    if cte.cancelado:
        raise CteFinanceiroErro(MSG_CANCELADO)
    if (cte.tp_amb or '').strip() == '2':
        raise CteFinanceiroErro(MSG_HOMOLOG)
    if not cte.apto_operacional or cte.status_conferencia not in (
        CTeHistoricoImportado.StatusConferencia.CONFERIDO,
        CTeHistoricoImportado.StatusConferencia.PREPARADO,
    ):
        raise CteFinanceiroErro(MSG_NAO_CONFERIDO)
    from apps.fiscal.cte_regra_fiscal import exigir_regra_fiscal_cte_ok

    try:
        exigir_regra_fiscal_cte_ok(cte)
    except ValueError as exc:
        raise CteFinanceiroErro(str(exc)) from exc


def titulos_vinculados_cte(cte: CTeHistoricoImportado) -> list[TituloFinanceiro]:
    return list(
        TituloFinanceiro.objects.filter(
            origem_tipo=TituloFinanceiro.OrigemTipo.CTE,
            origem_id=cte.pk,
            tipo=TituloFinanceiro.Tipo.PAGAR,
        ).order_by('id')
    )


def cnpj_credor_cte(cte: CTeHistoricoImportado) -> str:
    if cte.transportadora_id and cte.transportadora:
        return cnpj_apenas_digitos(cte.transportadora.cnpj)
    emit = cte.emit_json if isinstance(cte.emit_json, dict) else {}
    return cnpj_apenas_digitos(str(emit.get('CNPJ') or emit.get('cnpj') or ''))


def resolver_fornecedor_credor_cte(cte: CTeHistoricoImportado) -> Fornecedor | None:
    """Credor do frete = transportadora/emitente como Fornecedor (mesmo CNPJ)."""
    from apps.fiscal.fornecedor_entrada import buscar_fornecedores_por_cnpj

    cnpj = cnpj_credor_cte(cte)
    if len(cnpj) == 14:
        hits = buscar_fornecedores_por_cnpj(cnpj, apenas_ativos=False)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # Prefer ativo
            ativos = [f for f in hits if getattr(f, 'ativo', True)]
            return (ativos or hits)[0]
    if cte.transportadora_id:
        linked = Fornecedor.objects.filter(transportadora_padrao_id=cte.transportadora_id).first()
        if linked:
            return linked
    return None


def _valor_documento_nfe(chave: str, origem: str | None, documento_id: int | None) -> Decimal:
    if origem == 'BASE_NFE_ENTRADA_IMPORTADA' and documento_id:
        nf = NFeEntradaHistoricaImportada.objects.filter(pk=documento_id).only('valor_total_nf').first()
        if nf:
            return _round_money(nf.valor_total_nf or 0)
    if origem == 'BASE_NFE_SAIDA_IMPORTADA' and documento_id:
        nf = NFeSaidaHistoricaImportada.objects.filter(pk=documento_id).only('valor_total_nf').first()
        if nf:
            return _round_money(nf.valor_total_nf or 0)
    return Decimal('0')


def sugerir_rateio_frete_cte(cte: CTeHistoricoImportado) -> dict[str, Any]:
    """Monta sugestão proporcional ao valor das NF-es localizadas (ou partes iguais se valor zero)."""
    _cte_apto_financeiro(cte)
    base = valor_base_frete_cte(cte)
    if base <= 0:
        raise CteFinanceiroErro(MSG_VALOR_ZERO)

    docs = resolver_documentos_vinculados(cte)
    localizados = [d for d in docs if d.get('localizada') and d.get('chave_acesso')]
    if not localizados:
        # Rateio por chave mesmo sem documento localizado — partes iguais.
        chaves = [str(c).strip() for c in (cte.chaves_nfe_vinculadas or []) if str(c).strip()]
        if not chaves:
            raise CteFinanceiroErro(MSG_SEM_NFE)
        localizados = [
            {
                'chave_acesso': ch,
                'localizada': False,
                'origem': None,
                'origem_label': 'NF-e referenciada (não localizada)',
                'documento_id': None,
                'numero': None,
                'serie': None,
            }
            for ch in chaves
        ]

    pesos: list[Decimal] = []
    for d in localizados:
        pesos.append(
            _valor_documento_nfe(
                str(d.get('chave_acesso') or ''),
                d.get('origem'),
                d.get('documento_id'),
            )
        )
    soma_pesos = sum(pesos, Decimal('0'))
    metodo = 'PROPORCIONAL_VALOR_NFE' if soma_pesos > 0 else 'PARTES_IGUAIS'

    linhas: list[dict[str, Any]] = []
    alocado = Decimal('0')
    n = len(localizados)
    for i, d in enumerate(localizados):
        if metodo == 'PROPORCIONAL_VALOR_NFE':
            raw = (base * pesos[i] / soma_pesos) if soma_pesos > 0 else Decimal('0')
        else:
            raw = base / Decimal(n)
        valor = _round_money(raw)
        if i == n - 1:
            valor = _round_money(base - alocado)
        alocado += valor
        perc = _round_money((valor / base) * Decimal('100')) if base else Decimal('0')
        linhas.append(
            {
                'chave_acesso': d.get('chave_acesso'),
                'documento_id': d.get('documento_id'),
                'origem': d.get('origem'),
                'origem_label': d.get('origem_label'),
                'numero': d.get('numero'),
                'serie': d.get('serie'),
                'valor_documento': str(pesos[i]),
                'percentual': str(perc),
                'valor_frete': str(valor),
            }
        )

    impostos = resumo_impostos_cte_operacional(cte)
    return {
        'metodo': metodo,
        'valor_base': str(base),
        'linhas': linhas,
        'impostos_snapshot': impostos,
        'rateado': bool((cte.rateio_frete_json or {}).get('linhas')),
        'rateio_atual': cte.rateio_frete_json or {},
        'rateado_em': cte.rateado_em.isoformat() if cte.rateado_em else None,
    }


def _validar_linhas_rateio(linhas: list[dict], valor_base: Decimal) -> list[dict[str, Any]]:
    if not linhas:
        raise CteFinanceiroErro(MSG_RATEIO_VAZIO)
    out: list[dict[str, Any]] = []
    soma = Decimal('0')
    for raw in linhas:
        chave = str(raw.get('chave_acesso') or '').strip()
        if not chave:
            raise CteFinanceiroErro('Cada linha de rateio precisa da chave da NF-e.')
        valor = _round_money(raw.get('valor_frete') or 0)
        if valor < 0:
            raise CteFinanceiroErro('Valor de frete rateado não pode ser negativo.')
        soma += valor
        perc = _round_money((valor / valor_base) * Decimal('100')) if valor_base else Decimal('0')
        out.append(
            {
                'chave_acesso': chave,
                'documento_id': raw.get('documento_id'),
                'origem': raw.get('origem'),
                'origem_label': raw.get('origem_label') or '',
                'numero': raw.get('numero'),
                'serie': raw.get('serie'),
                'valor_documento': str(_round_money(raw.get('valor_documento') or 0)),
                'percentual': str(perc),
                'valor_frete': str(valor),
            }
        )
    if abs(soma - valor_base) > CENTAVO:
        raise CteFinanceiroErro(f'{MSG_RATEIO_SOMA} (soma={soma}, base={valor_base}).')
    return out


@transaction.atomic
def salvar_rateio_frete_cte(
    cte: CTeHistoricoImportado,
    *,
    linhas: list[dict],
    metodo: str = 'MANUAL',
    usuario=None,
) -> CTeHistoricoImportado:
    cte = CTeHistoricoImportado.objects.select_for_update(of=('self',)).get(pk=cte.pk)
    _cte_apto_financeiro(cte)
    base = valor_base_frete_cte(cte)
    if base <= 0:
        raise CteFinanceiroErro(MSG_VALOR_ZERO)
    linhas_ok = _validar_linhas_rateio(linhas, base)
    cte.rateio_frete_json = {
        'metodo': (metodo or 'MANUAL').strip() or 'MANUAL',
        'valor_base': str(base),
        'linhas': linhas_ok,
        'impostos_snapshot': resumo_impostos_cte_operacional(cte),
    }
    cte.rateado_em = timezone.now()
    cte.rateado_por = usuario if getattr(usuario, 'is_authenticated', False) else None
    cte.save(update_fields=['rateio_frete_json', 'rateado_em', 'rateado_por'])
    return cte


def montar_flags_financeiro_cte(cte: CTeHistoricoImportado) -> dict[str, Any]:
    titulos = titulos_vinculados_cte(cte)
    financeiro_gerado = bool(titulos)
    motivo = ''
    try:
        _cte_apto_financeiro(cte)
    except CteFinanceiroErro as exc:
        motivo = str(exc)
    if not motivo and financeiro_gerado:
        if any(t.cancelado for t in titulos):
            motivo = MSG_TITULO_CANCELADO
        else:
            motivo = MSG_JA_GERADO
    fornecedor = resolver_fornecedor_credor_cte(cte)
    if not motivo and not financeiro_gerado and not fornecedor:
        motivo = MSG_SEM_CREDOR
    base = valor_base_frete_cte(cte)
    if not motivo and not financeiro_gerado and base <= 0:
        motivo = MSG_VALOR_ZERO
    impostos = resumo_impostos_cte_operacional(cte)
    return {
        'financeiro_gerado': financeiro_gerado,
        'pode_gerar_contas_pagar': not financeiro_gerado and not motivo,
        'motivo_bloqueio_financeiro': motivo,
        'valor_frete_base': str(base),
        'fornecedor_credor_id': fornecedor.id if fornecedor else None,
        'fornecedor_credor_nome': fornecedor.razao_social if fornecedor else '',
        'fornecedor_credor_cnpj': cnpj_credor_cte(cte),
        'impostos': impostos,
        'rateio_salvo': bool((cte.rateio_frete_json or {}).get('linhas')),
        'contas_pagar_vinculadas': [
            {
                'id': t.id,
                'numero': t.numero,
                'status': t.status,
                'cancelado': t.cancelado,
                'tipo_lancamento': t.tipo_lancamento,
                'tipo_tributo': t.tipo_tributo,
                'valor_original': str(t.valor_original),
            }
            for t in titulos
        ],
    }


def preview_contas_pagar_cte(cte: CTeHistoricoImportado) -> dict[str, Any]:
    flags = montar_flags_financeiro_cte(cte)
    if flags['financeiro_gerado'] or not flags['pode_gerar_contas_pagar']:
        # ainda devolve preview informativo se bloqueado
        pass
    base = valor_base_frete_cte(cte)
    data_emissao = cte.dh_emissao.date() if cte.dh_emissao else date.today()
    venc = data_emissao + timedelta(days=30)
    impostos = flags['impostos']
    tributos: list[dict[str, Any]] = []
    for codigo, campo, label in (
        ('ICMS', 'icms_valor', 'ICMS do CT-e'),
        ('CBS', 'cbs_valor', 'CBS do CT-e'),
        ('IBS', 'ibs_valor', 'IBS do CT-e'),
    ):
        v = _round_money(impostos.get(campo) or 0)
        if v > 0:
            tributos.append({'tipo_tributo': codigo, 'label': label, 'valor': str(v)})
    return {
        **flags,
        'data_emissao': data_emissao.isoformat(),
        'vencimento_sugerido': venc.isoformat(),
        'parcela_frete': {
            'descricao': f'Frete CT-e {cte.numero}/{cte.serie or "1"}',
            'valor': str(base),
            'data_vencimento': venc.isoformat(),
        },
        'tributos_sugeridos': tributos,
        'aviso': (
            'A geração cria CP do frete (transportadora). '
            'Com «gerar impostos separados», cria títulos tributo adicionais (ICMS/CBS/IBS) sem baixar estoque.'
        ),
    }


def _validar_categoria(categoria_id: int | None) -> None:
    if categoria_id is None:
        return
    if not CategoriaFinanceira.objects.filter(pk=categoria_id, ativo=True).exists():
        raise CteFinanceiroErro('Categoria financeira inválida.')


def _validar_centro(centro_id: int | None) -> None:
    if centro_id is None:
        return
    if not CentroCusto.objects.filter(pk=centro_id, ativo=True).exists():
        raise CteFinanceiroErro('Centro de custo inválido.')


def _validar_conta(conta_id: int | None) -> None:
    if conta_id is None:
        return
    if not ContaFinanceira.objects.filter(pk=conta_id, ativo=True).exists():
        raise CteFinanceiroErro('Conta financeira inválida.')


def _sugerir_categoria_frete_id() -> int | None:
    for nome in ('Fretes e transportes', 'Serviços de terceiros', 'Despesas operacionais'):
        cat = (
            CategoriaFinanceira.objects.filter(nome__iexact=nome, ativo=True)
            .filter(tipo__in=(CategoriaFinanceira.Tipo.DESPESA, CategoriaFinanceira.Tipo.AMBOS))
            .first()
        )
        if cat:
            return cat.pk
    return None


@transaction.atomic
def gerar_contas_pagar_de_cte(
    cte: CTeHistoricoImportado,
    *,
    data_vencimento: date | str | None = None,
    gerar_impostos_separados: bool = True,
    categoria_id: int | None = None,
    centro_custo_id: int | None = None,
    forma_pagamento_prevista_codigo: str = '',
    conta_financeira_prevista_id: int | None = None,
    observacoes: str = '',
    usuario=None,
) -> dict[str, Any]:
    cte = CTeHistoricoImportado.objects.select_for_update(of=('self',)).get(pk=cte.pk)
    flags = montar_flags_financeiro_cte(cte)
    if not flags['pode_gerar_contas_pagar']:
        raise CteFinanceiroErro(flags.get('motivo_bloqueio_financeiro') or MSG_JA_GERADO)

    fornecedor = resolver_fornecedor_credor_cte(cte)
    if not fornecedor:
        raise CteFinanceiroErro(MSG_SEM_CREDOR)

    base = valor_base_frete_cte(cte)
    _validar_categoria(categoria_id)
    _validar_centro(centro_custo_id)
    _validar_conta(conta_financeira_prevista_id)
    if categoria_id is None:
        categoria_id = _sugerir_categoria_frete_id()

    data_emissao = cte.dh_emissao.date() if cte.dh_emissao else date.today()
    if data_vencimento:
        if isinstance(data_vencimento, str):
            venc = date.fromisoformat(data_vencimento[:10])
        else:
            venc = data_vencimento
    else:
        venc = data_emissao + timedelta(days=30)
    competencia = date(data_emissao.year, data_emissao.month, 1)
    origem_numero = f'{cte.numero}/{cte.serie or "1"}'
    impostos = resumo_impostos_cte_operacional(cte)
    obs_parts = [observacoes.strip()] if observacoes.strip() else []
    obs_parts.append(
        f'ICMS R$ {impostos["icms_valor"]:.2f} · CBS R$ {impostos["cbs_valor"]:.2f} · '
        f'IBS R$ {impostos["ibs_valor"]:.2f}'
    )
    if (cte.rateio_frete_json or {}).get('linhas'):
        obs_parts.append(f'Rateio salvo com {len(cte.rateio_frete_json["linhas"])} NF-e(s).')
    obs = ' | '.join(p for p in obs_parts if p)

    titulo_frete = criar_titulo_financeiro(
        tipo=TituloFinanceiro.Tipo.PAGAR,
        fornecedor_id=fornecedor.id,
        tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.SERVICO,
        descricao=f'Frete CT-e {origem_numero}',
        data_emissao=data_emissao,
        data_vencimento=venc,
        competencia=competencia,
        valor_original=base,
        origem_tipo=TituloFinanceiro.OrigemTipo.CTE,
        origem_id=cte.pk,
        origem_numero=origem_numero,
        origem_descricao=f'CT-e {origem_numero} — chave {cte.chave_acesso}',
        origem_data=data_emissao,
        documento_origem=f'CT-e nº {origem_numero}',
        forma_pagamento_prevista_codigo=forma_pagamento_prevista_codigo or '',
        conta_financeira_prevista_id=conta_financeira_prevista_id,
        categoria_id=categoria_id,
        centro_custo_id=centro_custo_id,
        observacoes=obs,
        parcelas_custom=[
            {
                'numero_parcela': 1,
                'data_vencimento': venc,
                'valor': base,
                'observacoes': '',
            }
        ],
        usuario=usuario,
    )

    titulos_extra: list[TituloFinanceiro] = []
    if gerar_impostos_separados:
        for codigo, campo in (('ICMS', 'icms_valor'), ('CBS', 'cbs_valor'), ('IBS', 'ibs_valor')):
            v = _round_money(impostos.get(campo) or 0)
            if v <= 0:
                continue
            titulos_extra.append(
                criar_titulo_financeiro(
                    tipo=TituloFinanceiro.Tipo.PAGAR,
                    tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.TRIBUTO_IMPOSTO,
                    tipo_tributo=codigo,
                    descricao=f'{codigo} CT-e {origem_numero}',
                    data_emissao=data_emissao,
                    data_vencimento=venc,
                    competencia=competencia,
                    valor_original=v,
                    origem_tipo=TituloFinanceiro.OrigemTipo.CTE,
                    origem_id=cte.pk,
                    origem_numero=origem_numero,
                    origem_descricao=f'Tributo {codigo} do CT-e {origem_numero}',
                    origem_data=data_emissao,
                    documento_origem=f'CT-e nº {origem_numero} ({codigo})',
                    observacoes=f'Gerado junto ao frete do CT-e {origem_numero}.',
                    parcelas_custom=[
                        {
                            'numero_parcela': 1,
                            'data_vencimento': venc,
                            'valor': v,
                            'observacoes': '',
                        }
                    ],
                    usuario=usuario,
                )
            )

    return {
        'titulo_frete_id': titulo_frete.id,
        'titulo_frete_numero': titulo_frete.numero,
        'titulos_tributo_ids': [t.id for t in titulos_extra],
        'flags': montar_flags_financeiro_cte(cte),
    }
