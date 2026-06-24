"""Painel operacional do produto — Centro de Informações (somente leitura)."""

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

LIMITE_HISTORICO = 10


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
        .select_related('nf__fornecedor', 'nf__pedido_compra')
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
        .select_related('nf__fornecedor', 'nf__pedido_compra')
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


def _listar_certificados_produto(produto_id: int) -> list[CertificadoQualidade]:
    return list(
        CertificadoQualidade.objects
        .select_related('cliente')
        .filter(itens__produto_id=produto_id)
        .distinct()
        .order_by('-data_emissao', '-criado_em')[:LIMITE_HISTORICO]
    )


def _serializar_certificado_cq(cq: CertificadoQualidade) -> dict:
    cliente = cq.cliente_nome_snapshot or (cq.cliente.razao_social if cq.cliente_id else '')
    return {
        'numero': cq.numero_formatado or cq.numero,
        'certificado_qualidade_id': cq.id,
        'cliente': cliente,
        'cliente_id': cq.cliente_id,
        'data': _iso_date(cq.data_emissao),
        'status': cq.status,
    }


def _buscar_ultimo_cq(produto_id: int, certificados: list[CertificadoQualidade] | None = None) -> dict | None:
    cqs = certificados if certificados is not None else _listar_certificados_produto(produto_id)[:1]
    if not cqs:
        return None
    return _serializar_certificado_cq(cqs[0])


def _buscar_ultima_corrida(produto: Produto) -> dict | None:
    corrida = (
        Corrida.objects
        .select_related('fornecedor')
        .filter(produto_id=produto.id)
        .order_by('-data_recebimento', '-id')
        .first()
    )
    rows = listar_corridas_disponiveis_produto(produto.id)
    if not corrida:
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


def _unit_venda_pedido(qty: Decimal, unit: Decimal, desconto: Decimal) -> tuple[Decimal, Decimal]:
    """Retorna (unitário exibido, unitário efetivo para inteligência)."""
    total = qty * unit - desconto
    if total < 0:
        total = Decimal('0')
    efetivo = (total / qty) if qty > 0 else Decimal('0')
    unit_exib = efetivo if desconto > 0 and qty > 0 else unit
    return unit_exib, efetivo


def _publicar_linha(linha: dict) -> dict:
    return {k: v for k, v in linha.items() if not k.startswith('_')}


def _coletar_linhas_compra(produto_id: int) -> list[dict]:
    linhas: list[dict] = []

    itens_pc = (
        ItemPedidoCompra.objects
        .select_related('pedido__fornecedor')
        .filter(produto_id=produto_id)
        .order_by('-pedido__data', '-id')
    )
    pedido_ids = [i.pedido_id for i in itens_pc]
    nfs_por_pedido: dict[int, NFeEntrada] = {}
    if pedido_ids:
        for nf in NFeEntrada.objects.filter(pedido_compra_id__in=pedido_ids).order_by('-data', '-id'):
            if nf.pedido_compra_id and nf.pedido_compra_id not in nfs_por_pedido:
                nfs_por_pedido[nf.pedido_compra_id] = nf

    for item_pc in itens_pc:
        pedido = item_pc.pedido
        nf = nfs_por_pedido.get(pedido.id)
        unit = Decimal(str(item_pc.valor_unitario or 0))
        qty = Decimal(str(item_pc.quantidade or 0))
        total = Decimal(str(item_pc.valor_total_item or 0))
        if total <= 0 and qty > 0:
            total = qty * unit
        linhas.append({
            'origem': 'pedido_compra',
            '_data_ordem': pedido.data,
            'data': _iso_date(pedido.data),
            'fornecedor': pedido.fornecedor.razao_social if pedido.fornecedor_id else '',
            'fornecedor_id': pedido.fornecedor_id,
            'nf': nf.numero if nf else None,
            'pedido_compra_id': pedido.id,
            'pedido_compra_numero': pedido.numero,
            'nf_entrada_id': nf.id if nf else None,
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_money(unit),
            'valor_total': _fmt_money(total),
            '_unit_decimal': unit,
        })

    for item_ne in (
        ItemNFeEntrada.objects
        .select_related('nf__fornecedor', 'nf__pedido_compra')
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')
    ):
        nf = item_ne.nf
        qty = Decimal(str(item_ne.quantidade or 0))
        total = Decimal(str(item_ne.valor or 0))
        unit = (total / qty) if qty > 0 else Decimal('0')
        linhas.append({
            'origem': 'nfe_entrada',
            '_data_ordem': nf.data,
            'data': _iso_date(nf.data),
            'fornecedor': nf.fornecedor.razao_social if nf.fornecedor_id else '',
            'fornecedor_id': nf.fornecedor_id,
            'nf': nf.numero,
            'pedido_compra_id': nf.pedido_compra_id,
            'pedido_compra_numero': nf.pedido_compra.numero if nf.pedido_compra_id else None,
            'nf_entrada_id': nf.id,
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_unit_price(total, qty),
            'valor_total': _fmt_money(total),
            '_unit_decimal': unit,
        })

    for item_conf in (
        ItemNFeEntradaConferencia.objects
        .select_related(
            'conferencia__nf_entrada_historica',
            'conferencia__nf_entrada_historica__fornecedor_emitente',
            'item_pedido_compra__pedido__fornecedor',
        )
        .filter(produto_id=produto_id)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .order_by('-conferencia__nf_entrada_historica__dh_emissao', '-id')
    ):
        if not item_conf.conferencia_id:
            continue
        nf_hist = item_conf.conferencia.nf_entrada_historica
        dt = nf_hist.dh_emissao.date() if nf_hist.dh_emissao else date.min
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
        unit = Decimal(str(item_conf.valor_unitario_nf or 0))
        qty = Decimal(str(item_conf.quantidade_nf or 0))
        total = Decimal(str(item_conf.valor_total_nf or 0))
        if total <= 0 and qty > 0:
            total = qty * unit
        linhas.append({
            'origem': 'nfe_entrada_conferencia',
            '_data_ordem': dt,
            'data': _iso_date(dt if dt != date.min else None),
            'fornecedor': fornecedor,
            'fornecedor_id': fornecedor_id,
            'nf': nf_hist.numero,
            'pedido_compra_id': pedido_pc.id if pedido_pc else None,
            'pedido_compra_numero': pedido_pc.numero if pedido_pc else None,
            'nf_entrada_historica_id': nf_hist.id,
            'conferencia_id': item_conf.conferencia_id,
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_money(unit),
            'valor_total': _fmt_money(total),
            '_unit_decimal': unit,
        })

    linhas.sort(key=lambda r: (r['_data_ordem'], r.get('nf_entrada_id') or r.get('nf_entrada_historica_id') or 0), reverse=True)
    return linhas


def _coletar_linhas_venda(produto_id: int) -> list[dict]:
    linhas: list[dict] = []

    for item_pv in (
        ItemPedidoVenda.objects
        .select_related('pedido__cliente')
        .filter(produto_id=produto_id)
        .order_by('-pedido__data', '-id')
    ):
        pedido = item_pv.pedido
        qty = Decimal(str(item_pv.quantidade or 0))
        unit = Decimal(str(item_pv.valor_unitario or 0))
        desconto = Decimal(str(item_pv.desconto or 0))
        unit_exib, unit_efetivo = _unit_venda_pedido(qty, unit, desconto)
        total = qty * unit - desconto
        if total < 0:
            total = Decimal('0')
        linhas.append({
            'origem': 'pedido_venda',
            '_data_ordem': pedido.data,
            'data': _iso_date(pedido.data),
            'cliente': pedido.cliente.razao_social if pedido.cliente_id else '',
            'cliente_id': pedido.cliente_id,
            'pedido_id': pedido.id,
            'pedido_numero': pedido.numero,
            'nf': None,
            'nf_id': None,
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_money(unit_exib),
            'valor_total': _fmt_money(total),
            '_unit_decimal': unit_efetivo,
        })

    for item_ns in (
        ItemNFeSaida.objects
        .select_related(
            'nf__cliente',
            'nf__pedido_venda',
            'item_faturamento_pedido__item_pedido__pedido',
        )
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')
    ):
        nf = item_ns.nf
        pedido = nf.pedido_venda
        if not pedido and item_ns.item_faturamento_pedido_id:
            item_pv_fat = item_ns.item_faturamento_pedido.item_pedido
            if item_pv_fat:
                pedido = item_pv_fat.pedido
        qty = Decimal(str(item_ns.quantidade or 0))
        total = Decimal(str(item_ns.valor or 0))
        unit = (total / qty) if qty > 0 else Decimal('0')
        linhas.append({
            'origem': 'nfe_saida',
            '_data_ordem': nf.data,
            'data': _iso_date(nf.data),
            'cliente': nf.cliente.razao_social if nf.cliente_id else '',
            'cliente_id': nf.cliente_id,
            'pedido_id': pedido.id if pedido else None,
            'pedido_numero': pedido.numero if pedido else None,
            'nf': nf.numero,
            'nf_id': nf.id,
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_unit_price(total, qty),
            'valor_total': _fmt_money(total),
            '_unit_decimal': unit,
        })

    linhas.sort(key=lambda r: (r['_data_ordem'], r.get('nf_id') or 0), reverse=True)
    return linhas


def _montar_inteligencia_preco(linhas: list[dict], *, campo_parte: str) -> dict | None:
    """campo_parte: fornecedor ou cliente."""
    precos = [
        (r['_unit_decimal'], r['_data_ordem'], r.get(campo_parte) or '', r)
        for r in linhas
        if r.get('_unit_decimal', Decimal('0')) > 0
    ]
    if not precos:
        return None

    menor = min(precos, key=lambda x: x[0])
    maior = max(precos, key=lambda x: x[0])
    ultimo = max(precos, key=lambda x: (x[1], x[3].get('nf_id') or x[3].get('nf_entrada_id') or 0))
    media = sum(p[0] for p in precos) / Decimal(len(precos))

    return {
        'menor_preco': _fmt_money(menor[0]),
        'maior_preco': _fmt_money(maior[0]),
        'preco_medio': f'{media:.4f}',
        'ultimo_preco': _fmt_money(ultimo[0]),
        f'{campo_parte}_menor_preco': menor[2],
        f'{campo_parte}_maior_preco': maior[2],
        f'{campo_parte}_ultimo_preco': ultimo[2],
        'data_ultimo_preco': _iso_date(ultimo[1]),
        'quantidade_registros': len(precos),
    }


def _montar_historico_compras(linhas: list[dict]) -> list[dict]:
    return [_publicar_linha(r) for r in linhas[:LIMITE_HISTORICO]]


def _montar_historico_vendas(linhas: list[dict]) -> list[dict]:
    return [_publicar_linha(r) for r in linhas[:LIMITE_HISTORICO]]


def _montar_inteligencia_compras(linhas: list[dict]) -> dict | None:
    return _montar_inteligencia_preco(linhas, campo_parte='fornecedor')


def _montar_inteligencia_vendas(linhas: list[dict]) -> dict | None:
    return _montar_inteligencia_preco(linhas, campo_parte='cliente')


def _montar_bloco_qualidade(produto: Produto, certificados: list[CertificadoQualidade] | None = None) -> dict:
    cqs = certificados if certificados is not None else _listar_certificados_produto(produto.id)
    certificados_out = [_serializar_certificado_cq(cq) for cq in cqs]

    corridas = []
    saldos = {
        ec.corrida_id: ec.saldo
        for ec in EstoqueCorrida.objects.filter(produto_id=produto.id).select_related('corrida')
    }
    for corrida in (
        Corrida.objects
        .select_related('fornecedor')
        .filter(produto_id=produto.id)
        .order_by('-data_recebimento', '-id')[:LIMITE_HISTORICO]
    ):
        saldo = saldos.get(corrida.id, Decimal('0'))
        corridas.append({
            'corrida': corrida.numero,
            'corrida_id': corrida.id,
            'fornecedor': corrida.fornecedor.razao_social if corrida.fornecedor_id else '',
            'fornecedor_id': corrida.fornecedor_id,
            'data_recebimento': _iso_date(corrida.data_recebimento),
            'saldo_atual': f'{saldo:.3f}',
            'nf_entrada': corrida.nf_entrada or '',
        })

    return {
        'certificados': certificados_out,
        'corridas': corridas,
    }


def _montar_bloco_fiscal(produto_id: int) -> dict:
    nf_entrada: list[dict] = []

    for item_ne in (
        ItemNFeEntrada.objects
        .select_related('nf__fornecedor')
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')[:LIMITE_HISTORICO]
    ):
        nf = item_ne.nf
        qty = Decimal(str(item_ne.quantidade or 0))
        total = Decimal(str(item_ne.valor or 0))
        nf_entrada.append({
            'origem': 'nfe_entrada',
            'numero': nf.numero,
            'nf_entrada_id': nf.id,
            'fornecedor': nf.fornecedor.razao_social if nf.fornecedor_id else '',
            'fornecedor_id': nf.fornecedor_id,
            'data': _iso_date(nf.data),
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_unit_price(total, qty),
            'valor_total': _fmt_money(total),
        })

    for item_conf in (
        ItemNFeEntradaConferencia.objects
        .select_related(
            'conferencia__nf_entrada_historica',
            'conferencia__nf_entrada_historica__fornecedor_emitente',
        )
        .filter(produto_id=produto_id)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .order_by('-conferencia__nf_entrada_historica__dh_emissao', '-id')[:LIMITE_HISTORICO]
    ):
        if not item_conf.conferencia_id:
            continue
        nf_hist = item_conf.conferencia.nf_entrada_historica
        dt = nf_hist.dh_emissao.date() if nf_hist.dh_emissao else None
        fornecedor = ''
        if nf_hist.fornecedor_emitente_id:
            fornecedor = nf_hist.fornecedor_emitente.razao_social
        qty = Decimal(str(item_conf.quantidade_nf or 0))
        total = Decimal(str(item_conf.valor_total_nf or 0))
        nf_entrada.append({
            'origem': 'nfe_entrada_conferencia',
            'numero': nf_hist.numero,
            'nf_entrada_historica_id': nf_hist.id,
            'conferencia_id': item_conf.conferencia_id,
            'fornecedor': fornecedor,
            'data': _iso_date(dt),
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_money(item_conf.valor_unitario_nf),
            'valor_total': _fmt_money(total),
        })

    nf_entrada.sort(key=lambda r: r.get('data') or '', reverse=True)
    nf_entrada = nf_entrada[:LIMITE_HISTORICO]

    nf_saida = []
    for item_ns in (
        ItemNFeSaida.objects
        .select_related('nf__cliente')
        .filter(produto_id=produto_id)
        .order_by('-nf__data', '-id')[:LIMITE_HISTORICO]
    ):
        nf = item_ns.nf
        qty = Decimal(str(item_ns.quantidade or 0))
        total = Decimal(str(item_ns.valor or 0))
        nf_saida.append({
            'numero': nf.numero,
            'nf_id': nf.id,
            'cliente': nf.cliente.razao_social if nf.cliente_id else '',
            'cliente_id': nf.cliente_id,
            'data': _iso_date(nf.data),
            'quantidade': f'{qty:.3f}',
            'valor_unitario': _fmt_unit_price(total, qty),
            'valor_total': _fmt_money(total),
        })

    return {
        'nf_entrada': nf_entrada,
        'nf_saida': nf_saida,
    }


def montar_painel_resumo_produto(produto: Produto) -> dict:
    """Agrega centro de informações do produto (somente leitura)."""
    pid = produto.id
    linhas_compra = _coletar_linhas_compra(pid)
    linhas_venda = _coletar_linhas_venda(pid)
    certificados = _listar_certificados_produto(pid)
    return {
        'produto': _montar_bloco_produto(produto),
        'estoque': _montar_bloco_estoque(produto),
        'ultima_compra': _buscar_ultima_compra(pid),
        'ultima_venda': _buscar_ultima_venda(pid),
        'ultima_nf_entrada': _buscar_ultima_nf_entrada(pid),
        'ultima_nf_saida': _buscar_ultima_nf_saida(pid),
        'ultimo_cq': _buscar_ultimo_cq(pid, certificados),
        'ultima_corrida': _buscar_ultima_corrida(produto),
        'historico_compras': _montar_historico_compras(linhas_compra),
        'historico_vendas': _montar_historico_vendas(linhas_venda),
        'inteligencia_compras': _montar_inteligencia_compras(linhas_compra),
        'inteligencia_vendas': _montar_inteligencia_vendas(linhas_venda),
        'qualidade': _montar_bloco_qualidade(produto, certificados),
        'fiscal': _montar_bloco_fiscal(pid),
    }
