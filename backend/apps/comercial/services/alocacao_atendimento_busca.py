"""ERP 4.0.13 — busca assistida para vínculos em AlocacaoAtendimento (payload leve, sem XML)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Q

from apps.cadastros.models import Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.cte_historico_conferencia import queryset_cte_entrada_operacional
from apps.fiscal.dfe_classificacao import (
    eh_documento_autorizado,
    eh_documento_homologacao,
    eh_documento_producao,
    metadados_classificacao_dfe,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaHistoricaImportada,
)


def _limite(params: dict[str, Any], *, padrao: int = 20, maximo: int = 50) -> int:
    try:
        n = int(params.get('limit') or padrao)
    except (TypeError, ValueError):
        n = padrao
    return max(1, min(n, maximo))


def _search(params: dict[str, Any]) -> str:
    return (params.get('search') or params.get('q') or '').strip()


def chave_acesso_resumida(chave: str | None) -> str:
    c = (chave or '').strip()
    if len(c) <= 12:
        return c
    return f'{c[:4]}…{c[-8:]}'


def _label_fornecedor(f: Fornecedor) -> str:
    nome = (f.nome_fantasia or f.razao_social or '').strip() or f'Fornecedor #{f.pk}'
    return nome


def buscar_fornecedores_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    qs = Fornecedor.objects.all().order_by('razao_social')
    term = _search(params)
    if term:
        qs = qs.filter(
            Q(razao_social__icontains=term)
            | Q(nome_fantasia__icontains=term)
            | Q(cnpj__icontains=term.replace('.', '').replace('/', '').replace('-', '')),
        )
    fid = params.get('fornecedor_id')
    if fid:
        try:
            qs = qs.filter(pk=int(fid))
        except (TypeError, ValueError):
            pass
    lim = _limite(params)
    return [
        {
            'id': f.pk,
            'label': _label_fornecedor(f),
            'cnpj': f.cnpj or '',
            'cidade': f.cidade or '',
            'uf': f.uf or '',
        }
        for f in qs[:lim]
    ]


def buscar_pedidos_compra_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    qs = PedidoCompra.objects.select_related('fornecedor').order_by('-data', '-id')
    term = _search(params)
    if term:
        qs = qs.filter(
            Q(numero__icontains=term)
            | Q(fornecedor__razao_social__icontains=term)
            | Q(fornecedor__nome_fantasia__icontains=term),
        )
    if params.get('fornecedor_id'):
        try:
            qs = qs.filter(fornecedor_id=int(params['fornecedor_id']))
        except (TypeError, ValueError):
            pass
    lim = _limite(params)
    out: list[dict[str, Any]] = []
    for pc in qs[:lim]:
        forn = _label_fornecedor(pc.fornecedor) if pc.fornecedor_id else '—'
        label = f'{pc.numero} — {forn}'
        out.append(
            {
                'id': pc.pk,
                'numero': pc.numero,
                'fornecedor': forn,
                'fornecedor_id': pc.fornecedor_id,
                'data': pc.data.isoformat() if pc.data else '',
                'status': pc.status or '',
                'valor_total': str(pc.valor_total),
                'label': label,
            },
        )
    return out


def _qtd_item_pc(item: ItemPedidoCompra) -> Decimal:
    return item.quantidade_negociada or item.quantidade or Decimal('0')


def buscar_pedidos_compra_itens_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    qs = ItemPedidoCompra.objects.select_related('pedido', 'pedido__fornecedor', 'produto').order_by('id')
    if params.get('pedido_compra_id'):
        try:
            qs = qs.filter(pedido_id=int(params['pedido_compra_id']))
        except (TypeError, ValueError):
            pass
    if params.get('fornecedor_id'):
        try:
            qs = qs.filter(pedido__fornecedor_id=int(params['fornecedor_id']))
        except (TypeError, ValueError):
            pass
    if params.get('produto_id'):
        try:
            qs = qs.filter(produto_id=int(params['produto_id']))
        except (TypeError, ValueError):
            pass
    term = _search(params)
    if term:
        qs = qs.filter(
            Q(produto__descricao__icontains=term)
            | Q(produto__codigo_completo__icontains=term)
            | Q(pedido__numero__icontains=term),
        )
    lim = _limite(params)
    out: list[dict[str, Any]] = []
    for it in qs[:lim]:
        qtd = _qtd_item_pc(it)
        un = (it.unidade_negociada or it.produto.unidade if it.produto_id else '') or 'UN'
        nome = (it.produto.descricao if it.produto_id else '') or '—'
        pc_num = it.pedido.numero if it.pedido_id else ''
        out.append(
            {
                'id': it.pk,
                'pedido_compra_id': it.pedido_id,
                'produto_id': it.produto_id,
                'produto_nome': nome,
                'quantidade': str(qtd),
                'quantidade_disponivel_para_vinculo': str(qtd),
                'unidade': un,
                'label': f'{nome} — {qtd} {un} — {pc_num}',
            },
        )
    return out


def _queryset_nfe_entrada_operacional(params: dict[str, Any]):
    qs = (
        NFeEntradaHistoricaImportada.objects.select_related(
            'fornecedor_emitente',
            'conferencia',
        )
        .filter(Q(tp_amb='1') | Q(tp_amb='') | Q(tp_amb__isnull=True))
        .exclude(tp_amb='2')
        .order_by('-dh_emissao', '-id')
    )
    somente_conf = str(params.get('somente_conferidas', 'true')).lower() not in {'0', 'false', 'nao', 'não'}
    if somente_conf:
        qs = qs.filter(conferencia__status__in=['CONFERIDA', 'PREPARADA'])
    incluir_div = str(params.get('incluir_divergentes', '')).lower() in {'1', 'true', 'sim'}
    if not incluir_div:
        qs = qs.exclude(conferencia__status='DIVERGENTE')
    return qs


def _nf_entrada_elegivel(nf: NFeEntradaHistoricaImportada, *, incluir_divergentes: bool) -> bool:
    if eh_documento_homologacao(nf):
        return False
    if not eh_documento_producao(nf):
        return False
    if not eh_documento_autorizado(nf):
        return False
    try:
        st = nf.conferencia.status
    except Exception:
        st = None
    if st == 'DIVERGENTE' and not incluir_divergentes:
        return False
    return True


def buscar_nfe_entrada_importada_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    qs = _queryset_nfe_entrada_operacional(params)
    term = _search(params)
    if term:
        qs = qs.filter(
            Q(chave_acesso__icontains=term)
            | Q(numero__icontains=term)
            | Q(fornecedor_emitente__razao_social__icontains=term)
            | Q(fornecedor_emitente__nome_fantasia__icontains=term),
        )
    if params.get('fornecedor_id'):
        try:
            qs = qs.filter(fornecedor_emitente_id=int(params['fornecedor_id']))
        except (TypeError, ValueError):
            pass
    if params.get('chave'):
        qs = qs.filter(chave_acesso__icontains=str(params['chave']).strip())
    if params.get('numero'):
        qs = qs.filter(numero__icontains=str(params['numero']).strip())
    incluir_div = str(params.get('incluir_divergentes', '')).lower() in {'1', 'true', 'sim'}
    lim = _limite(params)
    out: list[dict[str, Any]] = []
    for nf in qs[: lim * 3]:
        if len(out) >= lim:
            break
        if not _nf_entrada_elegivel(nf, incluir_divergentes=incluir_div):
            continue
        forn = ''
        if nf.fornecedor_emitente_id:
            forn = _label_fornecedor(nf.fornecedor_emitente)
        else:
            forn = (nf.emit_json or {}).get('xNome', '') or '—'
        try:
            conf_st = nf.conferencia.status
        except Exception:
            conf_st = None
        valor = nf.valor_total_nf
        label = f'NF-e {nf.numero}/{nf.serie or "—"} — {forn} — R$ {valor:.2f}'
        if conf_st:
            label += f' — {conf_st.title()}'
        out.append(
            {
                'id': nf.pk,
                'numero': nf.numero,
                'serie': nf.serie or '',
                'chave': nf.chave_acesso,
                'chave_resumida': chave_acesso_resumida(nf.chave_acesso),
                'fornecedor': forn,
                'fornecedor_id': nf.fornecedor_emitente_id,
                'emissao': nf.dh_emissao.date().isoformat() if nf.dh_emissao else '',
                'valor_total': str(valor),
                'status_conferencia': conf_st,
                'classificacao_dfe': metadados_classificacao_dfe(nf, conferencia_status=conf_st),
                'label': label,
            },
        )
    return out


def _prod_json_campos(prod_json: dict) -> dict[str, str]:
    pj = prod_json or {}
    return {
        'codigo': str(pj.get('cProd') or pj.get('codigo') or ''),
        'descricao': str(pj.get('xProd') or pj.get('descricao') or 'Item NF-e'),
        'ncm': str(pj.get('NCM') or pj.get('ncm') or ''),
        'cfop': str(pj.get('CFOP') or pj.get('cfop') or ''),
        'quantidade': str(pj.get('qCom') or pj.get('quantidade') or '0'),
        'unidade': str(pj.get('uCom') or pj.get('unidade') or 'UN'),
    }


def buscar_nfe_entrada_importada_itens_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    nf_id = params.get('nfe_entrada_historica_id') or params.get('nfe_entrada_id')
    qs = ItemNFeEntradaHistoricaImportada.objects.select_related(
        'nf',
        'nf__fornecedor_emitente',
        'item_conferencia',
        'item_conferencia__produto',
    ).order_by('nf_id', 'n_item')
    if nf_id:
        try:
            qs = qs.filter(nf_id=int(nf_id))
        except (TypeError, ValueError):
            pass
    if params.get('fornecedor_id'):
        try:
            qs = qs.filter(nf__fornecedor_emitente_id=int(params['fornecedor_id']))
        except (TypeError, ValueError):
            pass
    if params.get('produto_id'):
        try:
            pid = int(params['produto_id'])
            qs = qs.filter(
                Q(item_conferencia__produto_id=pid) | Q(item_conferencia__isnull=True),
            )
        except (TypeError, ValueError):
            pass
    term = _search(params)
    lim = _limite(params)
    out: list[dict[str, Any]] = []
    for it in qs[: lim * 2]:
        if len(out) >= lim:
            break
        nf = it.nf
        if not _nf_entrada_elegivel(nf, incluir_divergentes=True):
            continue
        campos = _prod_json_campos(it.prod_json)
        conf = getattr(it, 'item_conferencia', None)
        prod_id = conf.produto_id if conf else None
        prod_nome = (conf.produto.descricao if conf and conf.produto_id else None) or campos['descricao']
        if params.get('produto_id') and prod_id and prod_id != int(params['produto_id']):
            continue
        if term and term.lower() not in prod_nome.lower() and term.lower() not in campos['codigo'].lower():
            continue
        qtd = campos['quantidade']
        if conf and conf.quantidade_nf:
            qtd = str(conf.quantidade_nf)
        label = f'{prod_nome} — {qtd} {campos["unidade"]} — NF-e {nf.numero}'
        out.append(
            {
                'id': it.pk,
                'nfe_entrada_historica_id': nf.pk,
                'produto_id': prod_id,
                'produto_nome': prod_nome,
                'codigo': campos['codigo'],
                'ncm': campos['ncm'],
                'cfop': campos['cfop'],
                'quantidade': qtd,
                'valor_total': str(conf.valor_total_nf) if conf else '',
                'label': label,
            },
        )
    return out


def buscar_cte_conferido_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    qs = queryset_cte_entrada_operacional()
    term = _search(params)
    if term:
        qs = qs.filter(
            Q(chave_acesso__icontains=term)
            | Q(numero__icontains=term)
            | Q(transportadora__razao_social__icontains=term)
            | Q(transportadora__nome_fantasia__icontains=term),
        )
    if params.get('transportadora_id'):
        try:
            qs = qs.filter(transportadora_id=int(params['transportadora_id']))
        except (TypeError, ValueError):
            pass
    lim = _limite(params)
    out: list[dict[str, Any]] = []
    for cte in qs[:lim]:
        transp = ''
        if cte.transportadora_id:
            t = cte.transportadora
            transp = (t.nome_fantasia or t.razao_social or '').strip()
        tomador = ''
        if cte.empresa_tomadora_id:
            tomador = (cte.empresa_tomadora.razao_social or '').strip()
        valor = cte.valor_total_servico or Decimal('0')
        label = f'CT-e {cte.numero}/{cte.serie or "—"} — {transp or "Transportadora"} — R$ {valor:.2f} — Conferido'
        out.append(
            {
                'id': cte.pk,
                'numero': cte.numero,
                'serie': cte.serie or '',
                'transportadora': transp,
                'transportadora_id': cte.transportadora_id,
                'tomador': tomador,
                'valor_total': str(valor),
                'emissao': cte.dh_emissao.date().isoformat() if cte.dh_emissao else '',
                'status_conferencia': cte.status_conferencia,
                'label': label,
            },
        )
    return out
