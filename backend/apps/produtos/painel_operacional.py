"""Painel operacional do produto — Fase 1 (resumo somente leitura)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from apps.comercial.models import ItemPedidoCompra, ItemPedidoVenda
from apps.corridas.models import Corrida
from apps.fiscal.atendimento_estoque import montar_saldo_consolidado_produto
from apps.fiscal.models import (
    EstoqueCorrida,
    ItemNFeEntrada,
    ItemNFeEntradaConferencia,
    ItemNFeSaida,
    NFeEntrada,
)
from apps.produtos.models import Produto
from apps.produtos.serializers import ProdutoSerializer
from apps.produtos.snapshot import build_produto_snapshot
from apps.qualidade.corridas_disponiveis import listar_corridas_disponiveis_produto
from apps.qualidade.models import CertificadoQualidade


def _fmt_money(value) -> str:
    return f'{Decimal(str(value or 0)):.2f}'


def _fmt_unit_price(total, qty) -> str:
    q = Decimal(str(qty or 0))
    if q <= 0:
        return '0.00'
    return f'{(Decimal(str(total or 0)) / q):.4f}'


def _iso_date(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _montar_bloco_produto(produto: Produto) -> dict:
    ser_data = ProdutoSerializer(produto).data
    snap = build_produto_snapshot(produto)
    pp = snap.get('polegada_principal_snapshot') or ''
    ps = snap.get('polegada_secundaria_snapshot') or ''
    partes = [p for p in (pp, ps) if p]
    polegada = ' x '.join(partes) if partes else ''
    ncm_obj = ser_data.get('ncm_efetivo') or {}
    ncm = ''
    if isinstance(ncm_obj, dict):
        ncm = ncm_obj.get('codigo') or ''
    if not ncm:
        ncm = snap.get('ncm_codigo_snapshot') or ser_data.get('ncm') or ''
    material = ser_data.get('material_label') or snap.get('material_snapshot') or ser_data.get('material') or ''
    return {
        'id': produto.id,
        'codigo': produto.codigo_completo or ser_data.get('codigo_completo') or '',
        'descricao': produto.descricao,
        'material': material,
        'norma': snap.get('norma_snapshot') or produto.norma or '',
        'polegada': polegada,
        'ncm': ncm,
    }


def _montar_bloco_estoque(produto: Produto) -> dict:
    saldo = montar_saldo_consolidado_produto(produto)
    return {
        'saldo_fisico': saldo['saldo_fisico'],
        'reservado': saldo['quantidade_pendente_atendimento'],
        'disponivel': saldo['saldo_disponivel'],
    }


def _buscar_ultima_compra(produto_id: int) -> dict | None:
    candidatos: list[tuple[date, dict]] = []

    item_pc = (
        ItemPedidoCompra.objects
        .select_related('pedido__fornecedor')
        .filter(produto_id=produto_id)
        .order_by('-pedido__data', '-id')
        .first()
    )
    if item_pc:
        pedido = item_pc.pedido
        nf = (
            NFeEntrada.objects
            .filter(pedido_compra_id=pedido.id)
            .order_by('-data', '-id')
            .first()
        )
        candidatos.append((
            pedido.data,
            {
                'origem': 'pedido_compra',
                'fornecedor': pedido.fornecedor.razao_social if pedido.fornecedor_id else '',
                'fornecedor_id': pedido.fornecedor_id,
                'data': _iso_date(pedido.data),
                'valor_unitario': _fmt_money(item_pc.valor_unitario),
                'pedido_compra_id': pedido.id,
                'pedido_compra_numero': pedido.numero,
                'nf_entrada_id': nf.id if nf else None,
                'nf_entrada_numero': nf.numero if nf else None,
            },
        ))

    item_ne = (
        ItemNFeEntrada.objects
        .select_related('nf__fornecedor')
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')
        .first()
    )
    if item_ne:
        nf = item_ne.nf
        candidatos.append((
            nf.data,
            {
                'origem': 'nfe_entrada',
                'fornecedor': nf.fornecedor.razao_social if nf.fornecedor_id else '',
                'fornecedor_id': nf.fornecedor_id,
                'data': _iso_date(nf.data),
                'valor_unitario': _fmt_unit_price(item_ne.valor, item_ne.quantidade),
                'pedido_compra_id': nf.pedido_compra_id,
                'pedido_compra_numero': nf.pedido_compra.numero if nf.pedido_compra_id else None,
                'nf_entrada_id': nf.id,
                'nf_entrada_numero': nf.numero,
            },
        ))

    item_conf = (
        ItemNFeEntradaConferencia.objects
        .select_related(
            'conferencia__nf_entrada_historica',
            'conferencia__nf_entrada_historica__fornecedor_emitente',
            'item_pedido_compra__pedido__fornecedor',
        )
        .filter(produto_id=produto_id)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .order_by('-conferencia__nf_entrada_historica__dh_emissao', '-id')
        .first()
    )
    if item_conf and item_conf.conferencia_id:
        nf_hist = item_conf.conferencia.nf_entrada_historica
        dt = nf_hist.dh_emissao.date() if nf_hist.dh_emissao else None
        fornecedor = ''
        fornecedor_id = None
        if nf_hist.fornecedor_emitente_id:
            fornecedor = nf_hist.fornecedor_emitente.razao_social
            fornecedor_id = nf_hist.fornecedor_emitente_id
        pedido_pc = None
        if item_conf.item_pedido_compra_id:
            pedido_pc = item_conf.item_pedido_compra.pedido
            if not fornecedor and pedido_pc.fornecedor_id:
                fornecedor = pedido_pc.fornecedor.razao_social
                fornecedor_id = pedido_pc.fornecedor_id
        candidatos.append((
            dt or date.min,
            {
                'origem': 'nfe_entrada_conferencia',
                'fornecedor': fornecedor,
                'fornecedor_id': fornecedor_id,
                'data': _iso_date(dt),
                'valor_unitario': _fmt_money(item_conf.valor_unitario_nf),
                'pedido_compra_id': pedido_pc.id if pedido_pc else None,
                'pedido_compra_numero': pedido_pc.numero if pedido_pc else None,
                'nf_entrada_historica_id': nf_hist.id,
                'nf_entrada_numero': nf_hist.numero,
                'conferencia_id': item_conf.conferencia_id,
            },
        ))

    if not candidatos:
        return None
    candidatos.sort(key=lambda row: (row[0], row[1].get('nf_entrada_id') or 0), reverse=True)
    return candidatos[0][1]


def _buscar_ultima_venda(produto_id: int) -> dict | None:
    candidatos: list[tuple[date, dict]] = []

    item_pv = (
        ItemPedidoVenda.objects
        .select_related('pedido__cliente')
        .filter(produto_id=produto_id)
        .order_by('-pedido__data', '-id')
        .first()
    )
    if item_pv:
        pedido = item_pv.pedido
        candidatos.append((
            pedido.data,
            {
                'origem': 'pedido_venda',
                'cliente': pedido.cliente.razao_social if pedido.cliente_id else '',
                'cliente_id': pedido.cliente_id,
                'pedido_id': pedido.id,
                'pedido_numero': pedido.numero,
                'nf': None,
                'nf_id': None,
                'data': _iso_date(pedido.data),
            },
        ))

    item_ns = (
        ItemNFeSaida.objects
        .select_related(
            'nf__cliente',
            'nf__pedido_venda',
            'item_faturamento_pedido__item_pedido__pedido',
        )
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')
        .first()
    )
    if item_ns:
        nf = item_ns.nf
        pedido = nf.pedido_venda
        if not pedido and item_ns.item_faturamento_pedido_id:
            item_pv_fat = item_ns.item_faturamento_pedido.item_pedido
            if item_pv_fat:
                pedido = item_pv_fat.pedido
        candidatos.append((
            nf.data,
            {
                'origem': 'nfe_saida',
                'cliente': nf.cliente.razao_social if nf.cliente_id else '',
                'cliente_id': nf.cliente_id,
                'pedido_id': pedido.id if pedido else None,
                'pedido_numero': pedido.numero if pedido else None,
                'nf': nf.numero,
                'nf_id': nf.id,
                'data': _iso_date(nf.data),
            },
        ))

    if not candidatos:
        return None
    candidatos.sort(key=lambda row: row[0], reverse=True)
    return candidatos[0][1]


def _buscar_ultima_nf_entrada(produto_id: int) -> dict | None:
    candidatos: list[tuple[date, dict]] = []

    item_ne = (
        ItemNFeEntrada.objects
        .select_related('nf__fornecedor')
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')
        .first()
    )
    if item_ne:
        nf = item_ne.nf
        candidatos.append((
            nf.data,
            {
                'origem': 'nfe_entrada',
                'numero': nf.numero,
                'nf_entrada_id': nf.id,
                'fornecedor': nf.fornecedor.razao_social if nf.fornecedor_id else '',
                'fornecedor_id': nf.fornecedor_id,
                'data': _iso_date(nf.data),
                'quantidade': f'{item_ne.quantidade:.3f}',
                'valor_unitario': _fmt_unit_price(item_ne.valor, item_ne.quantidade),
            },
        ))

    item_conf = (
        ItemNFeEntradaConferencia.objects
        .select_related(
            'conferencia__nf_entrada_historica',
            'conferencia__nf_entrada_historica__fornecedor_emitente',
        )
        .filter(produto_id=produto_id)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .order_by('-conferencia__nf_entrada_historica__dh_emissao', '-id')
        .first()
    )
    if item_conf and item_conf.conferencia_id:
        nf_hist = item_conf.conferencia.nf_entrada_historica
        dt = nf_hist.dh_emissao.date() if nf_hist.dh_emissao else None
        fornecedor = ''
        fornecedor_id = None
        if nf_hist.fornecedor_emitente_id:
            fornecedor = nf_hist.fornecedor_emitente.razao_social
            fornecedor_id = nf_hist.fornecedor_emitente_id
        candidatos.append((
            dt or date.min,
            {
                'origem': 'nfe_entrada_conferencia',
                'numero': nf_hist.numero,
                'nf_entrada_historica_id': nf_hist.id,
                'conferencia_id': item_conf.conferencia_id,
                'fornecedor': fornecedor,
                'fornecedor_id': fornecedor_id,
                'data': _iso_date(dt),
                'quantidade': f'{item_conf.quantidade_nf:.3f}',
                'valor_unitario': _fmt_money(item_conf.valor_unitario_nf),
            },
        ))

    if not candidatos:
        return None
    candidatos.sort(key=lambda row: row[0], reverse=True)
    return candidatos[0][1]


def _buscar_ultima_nf_saida(produto_id: int) -> dict | None:
    item_ns = (
        ItemNFeSaida.objects
        .select_related('nf__cliente')
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')
        .first()
    )
    if not item_ns:
        return None
    nf = item_ns.nf
    return {
        'numero': nf.numero,
        'nf_id': nf.id,
        'cliente': nf.cliente.razao_social if nf.cliente_id else '',
        'cliente_id': nf.cliente_id,
        'data': _iso_date(nf.data),
        'quantidade': f'{item_ns.quantidade:.3f}',
        'valor_unitario': _fmt_unit_price(item_ns.valor, item_ns.quantidade),
    }


def _buscar_ultimo_cq(produto_id: int) -> dict | None:
    cq = (
        CertificadoQualidade.objects
        .select_related('cliente')
        .filter(itens__produto_id=produto_id)
        .distinct()
        .order_by('-data_emissao', '-criado_em')
        .first()
    )
    if not cq:
        return None
    cliente = cq.cliente_nome_snapshot or (cq.cliente.razao_social if cq.cliente_id else '')
    return {
        'numero': cq.numero_formatado or cq.numero,
        'certificado_qualidade_id': cq.id,
        'cliente': cliente,
        'cliente_id': cq.cliente_id,
        'data': _iso_date(cq.data_emissao),
        'status': cq.status,
    }


def _buscar_ultima_corrida(produto: Produto) -> dict | None:
    corrida = (
        Corrida.objects
        .select_related('fornecedor')
        .filter(produto_id=produto.id)
        .order_by('-data_recebimento', '-id')
        .first()
    )
    if not corrida:
        rows = listar_corridas_disponiveis_produto(produto.id)
        if not rows:
            return None
        row = rows[0]
        return {
            'corrida': row.get('corrida') or '',
            'corrida_id': None,
            'fornecedor': row.get('fornecedor') or '',
            'saldo_atual': row.get('saldo') or '0.000',
            'data_recebimento': None,
            'origem': row.get('origem'),
        }

    est = EstoqueCorrida.objects.filter(produto_id=produto.id, corrida_id=corrida.id).first()
    saldo = f'{est.saldo:.3f}' if est else '0.000'

    rows = listar_corridas_disponiveis_produto(produto.id)
    fornecedor = corrida.fornecedor.razao_social if corrida.fornecedor_id else ''
    for row in rows:
        if (row.get('corrida') or '').strip().upper() == (corrida.numero or '').strip().upper():
            saldo = row.get('saldo') or saldo
            if not fornecedor:
                fornecedor = row.get('fornecedor') or ''
            break

    return {
        'corrida': corrida.numero,
        'corrida_id': corrida.id,
        'fornecedor': fornecedor,
        'saldo_atual': saldo,
        'data_recebimento': _iso_date(corrida.data_recebimento),
    }


def montar_painel_resumo_produto(produto: Produto) -> dict:
    """Agrega resumo operacional somente leitura para o produto."""
    pid = produto.id
    return {
        'produto': _montar_bloco_produto(produto),
        'estoque': _montar_bloco_estoque(produto),
        'ultima_compra': _buscar_ultima_compra(pid),
        'ultima_venda': _buscar_ultima_venda(pid),
        'ultima_nf_entrada': _buscar_ultima_nf_entrada(pid),
        'ultima_nf_saida': _buscar_ultima_nf_saida(pid),
        'ultimo_cq': _buscar_ultimo_cq(pid),
        'ultima_corrida': _buscar_ultima_corrida(produto),
    }
