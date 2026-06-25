"""Painel de rastreabilidade do produto — somente leitura (consolidação de dados existentes)."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.corridas.models import Corrida
from apps.fiscal.models import (
    EstoqueCorrida,
    ItemNFeEntrada,
    ItemNFeEntradaConferencia,
    ItemNFeSaida,
    NFeEntrada,
)
from apps.produtos.models import Produto
from apps.produtos.painel_operacional import _iso_date
from apps.qualidade.models import ItemCertificadoFornecedorEntrada, ItemCertificadoQualidade

LIMITE_PADRAO = 20


def _norm_corrida(val: str | None) -> str:
    return (val or '').strip().upper()


def _decimal_to_float(value) -> float:
    return float(Decimal(str(value or 0)))


def _status_display(obj, field: str = 'status') -> str:
    display = getattr(obj, f'get_{field}_display', None)
    if callable(display):
        label = display()
        if label:
            return str(label)
    return str(getattr(obj, field, '') or '')


def _montar_corridas(produto: Produto, limite: int) -> list[dict]:
    corridas = list(
        Corrida.objects.filter(produto=produto)
        .select_related('fornecedor')
        .order_by('-data_recebimento', '-id')[:limite]
    )
    if not corridas:
        return []

    corrida_ids = [c.id for c in corridas]
    saldos = {
        row['corrida_id']: _decimal_to_float(row['saldo'])
        for row in EstoqueCorrida.objects.filter(corrida_id__in=corrida_ids)
        .values('corrida_id')
        .annotate(saldo=Sum('saldo'))
    }

    nf_por_corrida_id: dict[int, str] = {}
    for item in (
        ItemNFeEntrada.objects.filter(corrida_id__in=corrida_ids)
        .select_related('nf')
        .order_by('-nf__data', '-id')
    ):
        if item.corrida_id and item.corrida_id not in nf_por_corrida_id:
            nf_por_corrida_id[item.corrida_id] = item.nf.numero

    cf_por_corrida_id: set[int] = set()
    cf_por_corrida_num: set[str] = set()
    lotes_por_corrida_id: dict[int, str] = {}
    lotes_por_corrida_num: dict[str, str] = {}
    for row in (
        ItemCertificadoFornecedorEntrada.objects.filter(produto=produto, ativo=True)
        .values('corrida', 'lote', 'item_conferencia__corrida_estoque_id')
    ):
        corrida_fk = row['item_conferencia__corrida_estoque_id']
        corrida_txt = _norm_corrida(row['corrida'])
        if corrida_fk:
            cf_por_corrida_id.add(corrida_fk)
            if row['lote'] and corrida_fk not in lotes_por_corrida_id:
                lotes_por_corrida_id[corrida_fk] = row['lote']
        if corrida_txt:
            cf_por_corrida_num.add(corrida_txt)
            if row['lote'] and corrida_txt not in lotes_por_corrida_num:
                lotes_por_corrida_num[corrida_txt] = row['lote']

    for row in (
        ItemNFeEntradaConferencia.objects.filter(
            produto=produto,
            corrida_estoque_id__in=corrida_ids,
        )
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .values('corrida_estoque_id', 'lote')
    ):
        cid = row['corrida_estoque_id']
        if cid and row['lote'] and cid not in lotes_por_corrida_id:
            lotes_por_corrida_id[cid] = row['lote']

    for row in (
        ItemCertificadoQualidade.objects.filter(produto=produto)
        .values('corrida', 'lote', 'corrida_snapshot')
    ):
        corrida_txt = _norm_corrida(row['corrida'] or row['corrida_snapshot'])
        if corrida_txt and row['lote'] and corrida_txt not in lotes_por_corrida_num:
            lotes_por_corrida_num[corrida_txt] = row['lote']

    resultado: list[dict] = []
    for corrida in corridas:
        numero_norm = _norm_corrida(corrida.numero)
        nf_numero = (corrida.nf_entrada or '').strip() or nf_por_corrida_id.get(corrida.id, '')
        if nf_numero:
            origem_tecnica = f'NF-e {nf_numero}'
        else:
            origem_tecnica = 'Cadastro manual'

        lote = lotes_por_corrida_id.get(corrida.id) or lotes_por_corrida_num.get(numero_norm)

        resultado.append({
            'id': corrida.id,
            'codigo': corrida.numero,
            'lote': lote or None,
            'saldo': saldos.get(corrida.id, 0.0),
            'fornecedor_nome': (
                corrida.fornecedor.razao_social if corrida.fornecedor_id else None
            ),
            'origem_tecnica': origem_tecnica,
            'nf_entrada_numero': nf_numero or None,
            'possui_cf': corrida.id in cf_por_corrida_id or numero_norm in cf_por_corrida_num,
        })
    return resultado


def _montar_certificados_qualidade(
    produto: Produto,
    corridas_por_numero: dict[str, Corrida],
    limite: int,
) -> list[dict]:
    cert_map: dict[int, dict] = {}
    for item in (
        ItemCertificadoQualidade.objects.filter(produto=produto)
        .select_related('certificado__cliente')
        .order_by('-certificado__data_emissao', '-certificado__id', 'ordem', 'id')
    ):
        cq = item.certificado
        if cq.id not in cert_map:
            cliente_nome = ''
            if cq.cliente_id and cq.cliente:
                cliente_nome = cq.cliente.razao_social
            elif cq.cliente_nome_snapshot:
                cliente_nome = cq.cliente_nome_snapshot
            cert_map[cq.id] = {
                'id': cq.id,
                'numero': cq.numero_formatado or cq.numero or str(cq.id),
                'cliente_nome': cliente_nome or None,
                'data_emissao': _iso_date(cq.data_emissao),
                'status': _status_display(cq),
                'corridas': [],
                '_corrida_keys': set(),
            }

        codigo = (item.corrida or item.corrida_snapshot or '').strip()
        if not codigo:
            continue
        key = _norm_corrida(codigo)
        if key in cert_map[cq.id]['_corrida_keys']:
            continue
        cert_map[cq.id]['_corrida_keys'].add(key)
        corrida_obj = corridas_por_numero.get(key)
        cert_map[cq.id]['corridas'].append({
            'id': corrida_obj.id if corrida_obj else 0,
            'codigo': codigo,
        })

    resultado = []
    for entry in cert_map.values():
        entry.pop('_corrida_keys', None)
        resultado.append(entry)
    resultado.sort(key=lambda x: x['data_emissao'] or '', reverse=True)
    return resultado[:limite]


def _montar_certificados_fornecedor(
    produto: Produto,
    corridas_por_numero: dict[str, Corrida],
    limite: int,
) -> list[dict]:
    cert_map: dict[int, dict] = {}
    for item in (
        ItemCertificadoFornecedorEntrada.objects.filter(produto=produto, ativo=True)
        .select_related(
            'certificado_fornecedor__fornecedor',
            'certificado_fornecedor__nf_entrada_operacional',
            'item_conferencia__corrida_estoque',
        )
        .order_by('-certificado_fornecedor__criado_em', '-certificado_fornecedor__id', 'ordem', 'id')
    ):
        cf = item.certificado_fornecedor
        if cf.id not in cert_map:
            fornecedor_nome = ''
            if cf.fornecedor_id and cf.fornecedor:
                fornecedor_nome = cf.fornecedor.razao_social
            elif cf.fornecedor_nome_snapshot:
                fornecedor_nome = cf.fornecedor_nome_snapshot

            nf_ref = (cf.numero_nf_entrada or '').strip()
            if cf.nf_entrada_operacional_id and cf.nf_entrada_operacional:
                nf_ref = cf.nf_entrada_operacional.numero or nf_ref

            data_emissao = cf.data_nf_entrada
            if not data_emissao and item.data_certificado_fornecedor_item:
                data_emissao = item.data_certificado_fornecedor_item

            cert_map[cf.id] = {
                'id': cf.id,
                'numero': cf.numero_certificado_fornecedor or str(cf.id),
                'fornecedor_nome': fornecedor_nome,
                'data_emissao': _iso_date(data_emissao or cf.criado_em.date() if cf.criado_em else None),
                'corridas': [],
                'nf_entrada_referencia': nf_ref or None,
                '_corrida_keys': set(),
            }

        codigo = (item.corrida or '').strip()
        if not codigo and item.item_conferencia_id and item.item_conferencia:
            conf = item.item_conferencia
            codigo = (conf.corrida or '').strip()
            if not codigo and conf.corrida_estoque_id and conf.corrida_estoque:
                codigo = conf.corrida_estoque.numero
        if not codigo:
            continue

        key = _norm_corrida(codigo)
        if key in cert_map[cf.id]['_corrida_keys']:
            continue
        cert_map[cf.id]['_corrida_keys'].add(key)
        corrida_obj = corridas_por_numero.get(key)
        if not corrida_obj and item.item_conferencia_id and item.item_conferencia:
            corrida_obj = item.item_conferencia.corrida_estoque
        cert_map[cf.id]['corridas'].append({
            'id': corrida_obj.id if corrida_obj else 0,
            'codigo': codigo,
        })

    resultado = []
    for entry in cert_map.values():
        entry.pop('_corrida_keys', None)
        resultado.append(entry)
    resultado.sort(key=lambda x: x['data_emissao'] or '', reverse=True)
    return resultado[:limite]


def _montar_nfs_entrada(produto: Produto, corrida_ids: list[int], limite: int) -> list[dict]:
    vistos: dict[str, dict] = {}

    for item in (
        ItemNFeEntrada.objects.filter(produto=produto, corrida_id__in=corrida_ids)
        .select_related('nf__fornecedor', 'corrida')
        .order_by('-nf__data', '-id')
    ):
        nf = item.nf
        chave = f'op-{nf.id}'
        if chave in vistos:
            continue
        vistos[chave] = {
            'id': nf.id,
            'numero': nf.numero,
            'fornecedor_nome': nf.fornecedor.razao_social if nf.fornecedor_id else '',
            'data_entrada': _iso_date(nf.data),
            'corrida_codigo': item.corrida.numero if item.corrida_id else None,
            'status': _status_display(nf, 'status_operacional'),
        }

    for conf in (
        ItemNFeEntradaConferencia.objects.filter(produto=produto, corrida_estoque_id__in=corrida_ids)
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .select_related(
            'conferencia__nf_entrada_historica',
            'conferencia__nf_entrada_historica__fornecedor_emitente',
            'corrida_estoque',
        )
        .order_by('-conferencia__nf_entrada_historica__dh_emissao', '-id')
    ):
        nf_hist = conf.conferencia.nf_entrada_historica if conf.conferencia_id else None
        if not nf_hist:
            continue
        chave = f'hist-{nf_hist.id}'
        if chave in vistos:
            continue
        fornecedor_nome = ''
        if nf_hist.fornecedor_emitente_id and nf_hist.fornecedor_emitente:
            fornecedor_nome = nf_hist.fornecedor_emitente.razao_social
        dt = nf_hist.dh_emissao.date() if nf_hist.dh_emissao else None
        vistos[chave] = {
            'id': nf_hist.id,
            'numero': nf_hist.numero,
            'fornecedor_nome': fornecedor_nome,
            'data_entrada': _iso_date(dt),
            'corrida_codigo': (
                conf.corrida_estoque.numero if conf.corrida_estoque_id else (conf.corrida or None)
            ),
            'status': _status_display(conf.conferencia) if conf.conferencia_id else '',
        }

    numeros_texto = {
        (c.nf_entrada or '').strip()
        for c in Corrida.objects.filter(id__in=corrida_ids)
        if (c.nf_entrada or '').strip()
    }
    if numeros_texto:
        for nf in (
            NFeEntrada.objects.filter(numero__in=numeros_texto)
            .select_related('fornecedor')
            .order_by('-data', '-id')
        ):
            chave = f'op-{nf.id}'
            if chave in vistos:
                continue
            corrida_codigo = None
            corrida_match = (
                Corrida.objects.filter(produto=produto, nf_entrada=nf.numero)
                .order_by('-data_recebimento')
                .first()
            )
            if corrida_match:
                corrida_codigo = corrida_match.numero
            vistos[chave] = {
                'id': nf.id,
                'numero': nf.numero,
                'fornecedor_nome': nf.fornecedor.razao_social if nf.fornecedor_id else '',
                'data_entrada': _iso_date(nf.data),
                'corrida_codigo': corrida_codigo,
                'status': _status_display(nf, 'status_operacional'),
            }

    resultado = list(vistos.values())
    resultado.sort(key=lambda x: x['data_entrada'] or '', reverse=True)
    return resultado[:limite]


def _montar_nfs_saida(produto: Produto, limite: int) -> list[dict]:
    vistos: dict[int, dict] = {}
    for item in (
        ItemNFeSaida.objects.filter(produto=produto, corrida__isnull=False)
        .select_related('nf__cliente', 'nf__pedido_venda', 'corrida', 'item_faturamento_pedido__faturamento__pedido')
        .order_by('-nf__data', '-id')
    ):
        nf = item.nf
        if nf.id in vistos:
            continue

        pedido_numero = ''
        if nf.pedido_venda_id and nf.pedido_venda:
            pedido_numero = nf.pedido_venda.numero or str(nf.pedido_venda_id)
        elif item.item_faturamento_pedido_id and item.item_faturamento_pedido:
            fat = item.item_faturamento_pedido.faturamento
            if fat and fat.pedido_id:
                ped = fat.pedido
                pedido_numero = ped.numero or str(ped.id)

        cliente_nome = nf.cliente.razao_social if nf.cliente_id else ''

        vistos[nf.id] = {
            'id': nf.id,
            'numero': nf.numero,
            'cliente_nome': cliente_nome,
            'data_emissao': _iso_date(nf.data),
            'pedido_numero': pedido_numero or None,
            'corrida_codigo': item.corrida.numero if item.corrida_id else None,
        }

    resultado = list(vistos.values())
    resultado.sort(key=lambda x: x['data_emissao'] or '', reverse=True)
    return resultado[:limite]


def montar_painel_rastreabilidade(produto: Produto, limite_por_lista: int = LIMITE_PADRAO) -> dict:
    todas_corridas = list(
        Corrida.objects.filter(produto=produto).only('id', 'numero').order_by('-data_recebimento', '-id')
    )
    corridas_por_numero = {_norm_corrida(c.numero): c for c in todas_corridas}
    corrida_ids = [c.id for c in todas_corridas]

    return {
        'corridas': _montar_corridas(produto, limite_por_lista),
        'certificados_qualidade': _montar_certificados_qualidade(
            produto, corridas_por_numero, limite_por_lista
        ),
        'certificados_fornecedor': _montar_certificados_fornecedor(
            produto, corridas_por_numero, limite_por_lista
        ),
        'nfs_entrada': _montar_nfs_entrada(produto, corrida_ids, limite_por_lista),
        'nfs_saida': _montar_nfs_saida(produto, limite_por_lista),
    }
