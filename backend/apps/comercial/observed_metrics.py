from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.produtos.models import Produto
from apps.fiscal.consolidado_historico_gerencial import queryset_cte_historico_logistico
from apps.fiscal.consolidado_historico_gerencial import agrupar_cte_por_transportadora
from apps.fiscal.models import (
    CTeHistoricoImportado,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)
from apps.fiscal.nfe_historica_entrada_fiscal import (
    consolidar_queryset_entrada,
    queryset_compras_nf_entrada_historica,
    separar_totais_e_indicadores_entrada,
)
from apps.fiscal.nfe_historica_fiscal import (
    consolidar_queryset,
    queryset_faturamento_nf_saida_historica,
    separar_totais_e_indicadores,
)
from apps.fiscal.nfe_historica_periodo import PeriodoInvalido, resolver_periodo


def _to_dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


def _pct(num: Decimal, den: Decimal) -> float | None:
    if den <= 0:
        return None
    return float((num / den * Decimal('100')).quantize(Decimal('0.0001')))


def _norm_digits(value: str | None) -> str:
    return ''.join(c for c in str(value or '') if c.isdigit())


@dataclass
class ApoioGerencialResult:
    payload: dict[str, Any]


def _to_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def montar_apoio_gerencial(params) -> ApoioGerencialResult:
    try:
        di, df, meta = resolver_periodo(params)
    except PeriodoInvalido as exc:
        raise PeriodoInvalido(str(exc)) from exc

    empresa_id = params.get('empresa_id')
    fornecedor_id = params.get('fornecedor_id')
    transportadora_id = params.get('transportadora_id')
    produto_id = params.get('produto_id')

    qs_saida = queryset_faturamento_nf_saida_historica(
        NFeSaidaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
            cancelada=False,
        )
    )
    if empresa_id:
        qs_saida = qs_saida.filter(empresa_emitente_id=int(empresa_id))
    linha_saida = consolidar_queryset(qs_saida)
    tot_saida, ind_saida = separar_totais_e_indicadores(linha_saida)

    qs_entrada = queryset_compras_nf_entrada_historica(
        NFeEntradaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        )
    )
    if empresa_id:
        qs_entrada = qs_entrada.filter(empresa_destinataria_id=int(empresa_id))
    if fornecedor_id:
        qs_entrada = qs_entrada.filter(fornecedor_emitente_id=int(fornecedor_id))
    linha_entrada = consolidar_queryset_entrada(qs_entrada)
    tot_entrada, ind_entrada = separar_totais_e_indicadores_entrada(linha_entrada)

    qs_cte = queryset_cte_historico_logistico(
        CTeHistoricoImportado.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
            cancelado=False,
        )
    )
    if empresa_id:
        qs_cte = qs_cte.filter(empresa_tomadora_id=int(empresa_id))
    if transportadora_id:
        qs_cte = qs_cte.filter(transportadora_id=int(transportadora_id))

    valor_total_frete = sum(
        (cte.valor_total_servico or Decimal('0') for cte in qs_cte.iterator(chunk_size=500)),
        Decimal('0'),
    )
    qtd_cte = qs_cte.count()
    frete_medio = float((valor_total_frete / Decimal(qtd_cte)).quantize(Decimal('0.01'))) if qtd_cte > 0 else 0.0
    frete_sobre_faturamento_pct = _pct(valor_total_frete, _to_dec(tot_saida['faturamento_bruto']))

    custo_medio_compra_observado = 0.0
    if int(tot_entrada['quantidade_notas']) > 0:
        custo_medio_compra_observado = float(
            (_to_dec(tot_entrada['valor_total_compras']) / Decimal(int(tot_entrada['quantidade_notas']))).quantize(Decimal('0.01'))
        )

    custo_medio_produto = None
    if produto_id:
        produto = Produto.objects.filter(pk=int(produto_id)).only('id', 'ncm', 'familia_id').select_related('familia__ncm_padrao').first()
        ncm = _norm_digits(produto.get_ncm_efetivo_codigo() if produto else '')
        if ncm:
            itens = ItemNFeEntradaHistoricaImportada.objects.filter(nf__in=qs_entrada).values_list('prod_json', flat=True)
            total_valor = Decimal('0')
            total_qtd = Decimal('0')
            for prod_json in itens.iterator(chunk_size=1000):
                if not isinstance(prod_json, dict):
                    continue
                ncm_item = _norm_digits(prod_json.get('NCM') or prod_json.get('ncm') or '')
                if ncm_item != ncm:
                    continue
                qtd = _to_dec(prod_json.get('qCom') or prod_json.get('qTrib') or 0)
                v_unit = _to_dec(prod_json.get('vUnCom') or prod_json.get('vUnTrib') or 0)
                if qtd > 0 and v_unit >= 0:
                    total_qtd += qtd
                    total_valor += qtd * v_unit
            if total_qtd > 0:
                custo_medio_produto = float((total_valor / total_qtd).quantize(Decimal('0.01')))

    margem_referencia = 0.0
    faturamento_dec = _to_dec(tot_saida['faturamento_bruto'])
    compras_dec = _to_dec(tot_entrada['valor_total_compras'])
    fretes_dec = valor_total_frete
    if faturamento_dec > 0:
        margem_referencia = float(((faturamento_dec - compras_dec - fretes_dec) / faturamento_dec * Decimal('100')).quantize(Decimal('0.01')))

    payload = {
        'periodo': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
        'referencia_historica': {
            'frete_medio_sobre_faturamento_pct': frete_sobre_faturamento_pct,
            'frete_medio_valor': frete_medio,
            'carga_tributaria_media_vendas_pct': ind_saida.get('carga_tributaria_media_total_observada_pct'),
            'carga_tributaria_media_compras_pct': ind_entrada.get('carga_tributaria_media_total_observada_pct'),
            'custo_medio_compra_observado_por_nota': custo_medio_compra_observado,
            'custo_medio_compra_observado_produto': custo_medio_produto,
            'margem_referencia_observada_pct': margem_referencia,
        },
        'comparativo_periodo': {
            'faturamento': float(faturamento_dec.quantize(Decimal('0.01'))),
            'compras': float(compras_dec.quantize(Decimal('0.01'))),
            'fretes': float(fretes_dec.quantize(Decimal('0.01'))),
            'diferenca_venda_compra': float((faturamento_dec - compras_dec).quantize(Decimal('0.01'))),
        },
        'mensagens': {
            'contexto': 'Dados de referência histórica para apoio gerencial. Não substituem a regra comercial principal.',
            'rotulo_referencia': 'média observada',
        },
    }
    return ApoioGerencialResult(payload=payload)


def montar_referencia_comercial_frete(params) -> ApoioGerencialResult:
    try:
        di, df, meta = resolver_periodo(params)
    except PeriodoInvalido as exc:
        raise PeriodoInvalido(str(exc)) from exc

    empresa_id = _to_int(params.get('empresa_id'))
    transportadora_id = _to_int(params.get('transportadora_id'))

    qs_cte = queryset_cte_historico_logistico(
        CTeHistoricoImportado.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
            cancelado=False,
        ).select_related('transportadora', 'empresa_tomadora')
    )
    if empresa_id:
        qs_cte = qs_cte.filter(empresa_tomadora_id=empresa_id)
    if transportadora_id:
        qs_cte = qs_cte.filter(transportadora_id=transportadora_id)

    valor_total_fretes = sum(
        (cte.valor_total_servico or Decimal('0') for cte in qs_cte.iterator(chunk_size=500)),
        Decimal('0'),
    )
    quantidade_ctes_validos = qs_cte.count()
    frete_medio_observado = (
        float((valor_total_fretes / Decimal(quantidade_ctes_validos)).quantize(Decimal('0.01')))
        if quantidade_ctes_validos > 0
        else None
    )

    qs_faturamento = queryset_faturamento_nf_saida_historica(
        NFeSaidaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
            cancelada=False,
        )
    )
    if empresa_id:
        qs_faturamento = qs_faturamento.filter(empresa_emitente_id=empresa_id)
    tot_faturamento, _ = separar_totais_e_indicadores(consolidar_queryset(qs_faturamento))
    faturamento_periodo = _to_dec(tot_faturamento['faturamento_bruto'])
    peso_frete_sobre_faturamento = _pct(valor_total_fretes, faturamento_periodo)

    transportadora_referencia = None
    if transportadora_id:
        row = qs_cte.first()
        nome = ''
        if row and row.transportadora_id and row.transportadora:
            nome = row.transportadora.razao_social
        transportadora_referencia = {
            'transportadora_id': transportadora_id,
            'transportadora_nome': nome or 'Transportadora selecionada',
        }

    payload = {
        'periodo_utilizado': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
        'empresa_utilizada': {'empresa_id': empresa_id},
        'referencia_historica': {
            'frete_medio_observado': frete_medio_observado,
            'peso_frete_sobre_faturamento': peso_frete_sobre_faturamento,
            'valor_total_fretes_periodo': float(valor_total_fretes.quantize(Decimal('0.01'))),
            'quantidade_ctes_validos': quantidade_ctes_validos,
            'transportadora_referencia': transportadora_referencia,
            'frete_medio_por_transportadora': agrupar_cte_por_transportadora(qs_cte),
        },
        'mensagem': (
            'Referência histórica observada para apoio gerencial.'
            if quantidade_ctes_validos > 0
            else 'Sem base histórica suficiente de CT-e no período/filtro para calcular referência comercial de frete.'
        ),
        'tem_base_historica': quantidade_ctes_validos > 0,
    }
    return ApoioGerencialResult(payload=payload)


def _descricao_produto(prod_json: dict[str, Any]) -> str:
    return str(
        (prod_json.get('xProd') or prod_json.get('xprod') or prod_json.get('descricao') or '')
    ).strip()


def _unit_price_produto(prod_json: dict[str, Any]) -> Decimal:
    return _to_dec(prod_json.get('vUnCom') or prod_json.get('vUnTrib') or prod_json.get('vProd') or 0)


def _quantidade_produto(prod_json: dict[str, Any]) -> Decimal:
    return _to_dec(prod_json.get('qCom') or prod_json.get('qTrib') or 0)


def _fornecedor_nome(nf: NFeEntradaHistoricaImportada) -> str:
    if nf.fornecedor_emitente_id and nf.fornecedor_emitente:
        return nf.fornecedor_emitente.razao_social
    emit = nf.emit_json if isinstance(nf.emit_json, dict) else {}
    return str(emit.get('xNome') or '').strip()


def montar_referencia_comercial_custo_compra(params) -> ApoioGerencialResult:
    try:
        di, df, meta = resolver_periodo(params)
    except PeriodoInvalido as exc:
        raise PeriodoInvalido(str(exc)) from exc

    empresa_id = _to_int(params.get('empresa_id'))
    fornecedor_id = _to_int(params.get('fornecedor_id'))
    produto_id = _to_int(params.get('produto_id'))
    ncm_filtro = _norm_digits(params.get('ncm'))

    produto = (
        Produto.objects.filter(pk=produto_id).only('id', 'ncm', 'familia_id').select_related('familia__ncm_padrao').first()
        if produto_id
        else None
    )
    ncm_produto = _norm_digits(produto.get_ncm_efetivo_codigo() if produto else '')
    ncm_target = ncm_filtro or ncm_produto

    qs_entrada = queryset_compras_nf_entrada_historica(
        NFeEntradaHistoricaImportada.objects.filter(
            dh_emissao__date__gte=di,
            dh_emissao__date__lte=df,
        ).select_related('fornecedor_emitente', 'empresa_destinataria')
    ).exclude(cstat__in=['101', '135', '155'])
    if empresa_id:
        qs_entrada = qs_entrada.filter(empresa_destinataria_id=empresa_id)
    if fornecedor_id:
        qs_entrada = qs_entrada.filter(fornecedor_emitente_id=fornecedor_id)

    itens_qs = ItemNFeEntradaHistoricaImportada.objects.filter(nf__in=qs_entrada).select_related('nf')
    total_valor = Decimal('0')
    total_qtd = Decimal('0')
    quantidade_itens_base = 0
    notas_ids: set[int] = set()
    ultimo_custo_observado: float | None = None
    ultimo_custo_data = None
    fornecedor_referencia = ''

    for item in itens_qs.iterator(chunk_size=1000):
        prod_json = item.prod_json if isinstance(item.prod_json, dict) else {}
        ncm_item = _norm_digits(prod_json.get('NCM') or prod_json.get('ncm'))
        if ncm_target and ncm_item != ncm_target:
            continue

        qtd = _quantidade_produto(prod_json)
        v_unit = _unit_price_produto(prod_json)
        if qtd <= 0 or v_unit <= 0:
            continue

        quantidade_itens_base += 1
        notas_ids.add(item.nf_id)
        total_qtd += qtd
        total_valor += (qtd * v_unit)

        dh = item.nf.dh_emissao
        if (ultimo_custo_data is None) or (dh and dh > ultimo_custo_data):
            ultimo_custo_data = dh
            ultimo_custo_observado = float(v_unit.quantize(Decimal('0.01')))
            fornecedor_referencia = _fornecedor_nome(item.nf)

    custo_medio_observado = None
    if total_qtd > 0:
        custo_medio_observado = float((total_valor / total_qtd).quantize(Decimal('0.01')))

    tem_base = (custo_medio_observado is not None) and (quantidade_itens_base > 0)
    mensagem = (
        'Referência histórica observada de custo de compra para apoio gerencial.'
        if tem_base
        else 'Sem base histórica suficiente de compras no período/filtro para calcular referência de custo observado.'
    )

    payload = {
        'periodo_utilizado': {'data_inicio': di.isoformat(), 'data_fim': df.isoformat(), **meta},
        'empresa_utilizada': {'empresa_id': empresa_id},
        'referencia_historica': {
            'custo_medio_observado': custo_medio_observado,
            'ultimo_custo_observado': ultimo_custo_observado,
            'quantidade_notas_base': len(notas_ids),
            'quantidade_itens_base': quantidade_itens_base,
            'fornecedor_referencia': fornecedor_referencia or None,
            'produto_referencia': {'produto_id': produto_id, 'ncm_utilizado': ncm_target or None},
        },
        'tem_base_historica': tem_base,
        'mensagem': mensagem,
    }
    return ApoioGerencialResult(payload=payload)
