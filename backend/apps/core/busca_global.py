"""Busca global simples — ERP 4.0.14.9.3."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from django.db.models import Q

from apps.cadastros.models import Cliente, Colaborador, Empresa, Fornecedor
from apps.comercial.models import PedidoCompra, PedidoVenda, Proposta
from apps.core.pdf.formatters import format_cnpj, format_currency_br
from apps.financeiro.models import CreditoFinanceiro, TituloFinanceiro
from apps.fiscal.models import NFeEntrada, NFeEntradaConferencia, NFeEntradaHistoricaImportada, NFeSaida
from apps.produtos.models import Produto

MIN_QUERY_LEN = 2
MAX_POR_TIPO = 5
MAX_TOTAL = 40

GRUPO_LABELS = {
    'cliente': 'Clientes',
    'fornecedor': 'Fornecedores',
    'produto': 'Produtos',
    'colaborador': 'Colaboradores',
    'empresa': 'Cadastros',
    'proposta': 'Documentos',
    'pedido_venda': 'Documentos',
    'pedido_compra': 'Documentos',
    'nfe_saida': 'Documentos',
    'nfe_entrada': 'Documentos',
    'conta_receber': 'Financeiro',
    'conta_pagar': 'Financeiro',
    'credito': 'Financeiro',
}


def _digits(value: str) -> str:
    return re.sub(r'\D', '', value or '')


def _item(
    *,
    tipo: str,
    tipo_label: str,
    titulo: str,
    subtitulo: str,
    url: str,
) -> dict[str, str]:
    return {
        'tipo': tipo,
        'tipo_label': tipo_label,
        'grupo': GRUPO_LABELS.get(tipo, 'Outros'),
        'titulo': titulo,
        'subtitulo': subtitulo,
        'url': url,
    }


def _buscar_clientes(q: str, q_digits: str) -> list[dict[str, str]]:
    filtro = Q(razao_social__icontains=q) | Q(nome_fantasia__icontains=q)
    if q_digits:
        filtro |= Q(cnpj__icontains=q_digits)
    out = []
    for c in Cliente.objects.filter(filtro).order_by('razao_social')[:MAX_POR_TIPO]:
        titulo = (c.nome_fantasia or c.razao_social).strip()
        out.append(
            _item(
                tipo='cliente',
                tipo_label='Cliente',
                titulo=titulo,
                subtitulo=f'CNPJ: {format_cnpj(c.cnpj)}',
                url=f'/clientes/{c.pk}/edit',
            ),
        )
    return out


def _buscar_fornecedores(q: str, q_digits: str) -> list[dict[str, str]]:
    filtro = Q(razao_social__icontains=q) | Q(nome_fantasia__icontains=q)
    if q_digits:
        filtro |= Q(cnpj__icontains=q_digits)
    out = []
    for f in Fornecedor.objects.filter(filtro).order_by('razao_social')[:MAX_POR_TIPO]:
        titulo = (f.nome_fantasia or f.razao_social).strip()
        out.append(
            _item(
                tipo='fornecedor',
                tipo_label='Fornecedor',
                titulo=titulo,
                subtitulo=f'CNPJ: {format_cnpj(f.cnpj)}',
                url=f'/fornecedores/{f.pk}/edit',
            ),
        )
    return out


def _buscar_produtos(q: str) -> list[dict[str, str]]:
    filtro = Q(descricao__icontains=q) | Q(codigo_completo__icontains=q) | Q(ncm__icontains=q)
    out = []
    for p in Produto.objects.filter(filtro).order_by('descricao')[:MAX_POR_TIPO]:
        codigo = (p.codigo_completo or '').strip() or '—'
        out.append(
            _item(
                tipo='produto',
                tipo_label='Produto',
                titulo=p.descricao[:120],
                subtitulo=f'Código: {codigo}',
                url=f'/produtos?produto={p.pk}',
            ),
        )
    return out


def _buscar_colaboradores(q: str) -> list[dict[str, str]]:
    filtro = Q(nome__icontains=q) | Q(codigo__icontains=q) | Q(email__icontains=q)
    out = []
    for c in Colaborador.objects.filter(filtro).order_by('nome')[:MAX_POR_TIPO]:
        out.append(
            _item(
                tipo='colaborador',
                tipo_label='Colaborador',
                titulo=c.nome,
                subtitulo=(c.email or c.codigo or '—')[:80],
                url='/colaboradores',
            ),
        )
    return out


def _buscar_empresas(q: str, q_digits: str) -> list[dict[str, str]]:
    filtro = Q(razao_social__icontains=q) | Q(nome_fantasia__icontains=q)
    if q_digits:
        filtro |= Q(cnpj__icontains=q_digits)
    out = []
    for e in Empresa.objects.filter(filtro).order_by('razao_social')[:MAX_POR_TIPO]:
        titulo = (e.nome_fantasia or e.razao_social).strip()
        out.append(
            _item(
                tipo='empresa',
                tipo_label='Empresa',
                titulo=titulo,
                subtitulo=f'CNPJ: {format_cnpj(e.cnpj)}',
                url='/empresas',
            ),
        )
    return out


def _buscar_propostas(q: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    out = []
    qs = filtrar_queryset_por_numeros_documento(
        Proposta.objects.select_related('cliente'),
        q,
        'numero',
    ).order_by('-data')[:MAX_POR_TIPO]
    for p in qs:
        cliente = p.cliente.razao_social if p.cliente_id else (p.cliente_avulso_nome or '—')
        out.append(
            _item(
                tipo='proposta',
                tipo_label='Proposta',
                titulo=f'Proposta {p.numero}',
                subtitulo=str(cliente)[:80],
                url=f'/propostas?proposta={p.pk}',
            ),
        )
    return out


def _buscar_pedidos_venda(q: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    out = []
    qs = filtrar_queryset_por_numeros_documento(
        PedidoVenda.objects.select_related('cliente'),
        q,
        'numero',
    ).order_by('-data')[:MAX_POR_TIPO]
    for pv in qs:
        out.append(
            _item(
                tipo='pedido_venda',
                tipo_label='Pedido de Venda',
                titulo=f'Pedido {pv.numero}',
                subtitulo=(pv.cliente.razao_social if pv.cliente_id else '—')[:80],
                url=f'/pedidos-venda?pedido={pv.pk}',
            ),
        )
    return out


def _buscar_pedidos_compra(q: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    out = []
    qs = filtrar_queryset_por_numeros_documento(
        PedidoCompra.objects.select_related('fornecedor'),
        q,
        'numero',
    ).order_by('-data')[:MAX_POR_TIPO]
    for pc in qs:
        out.append(
            _item(
                tipo='pedido_compra',
                tipo_label='Pedido de Compra',
                titulo=f'Pedido {pc.numero}',
                subtitulo=(pc.fornecedor.razao_social if pc.fornecedor_id else '—')[:80],
                url=f'/pedidos-compra?pedido={pc.pk}',
            ),
        )
    return out


def _buscar_nfe_saida(q: str, q_digits: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    q_extra = Q(status__icontains=q)
    if len(q_digits) >= 4:
        q_extra |= Q(chave_acesso__icontains=q_digits)
    qs = filtrar_queryset_por_numeros_documento(
        NFeSaida.objects.select_related('cliente'),
        q,
        'numero',
        q_extra=q_extra,
    )
    out = []
    for nf in qs.order_by('-data')[:MAX_POR_TIPO]:
        status = (nf.status_emissao_sefaz or nf.status or '').replace('_', ' ').title() or '—'
        out.append(
            _item(
                tipo='nfe_saida',
                tipo_label='NF-e Saída',
                titulo=f'NF-e nº {nf.numero}',
                subtitulo=f'{(nf.cliente.razao_social if nf.cliente_id else "—")[:40]} · {status}',
                url=f'/nfe-saida?nfe={nf.pk}',
            ),
        )
    return out


def _buscar_nfe_entrada(q: str, q_digits: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    out: list[dict[str, str]] = []
    qs_op = filtrar_queryset_por_numeros_documento(
        NFeEntrada.objects.select_related('fornecedor'),
        q,
        'numero',
    ).order_by('-data')[:MAX_POR_TIPO]
    for nf in qs_op:
        out.append(
            _item(
                tipo='nfe_entrada',
                tipo_label='NF-e Entrada',
                titulo=f'NF-e Entrada nº {nf.numero}',
                subtitulo=(nf.fornecedor.razao_social if nf.fornecedor_id else '—')[:80],
                url='/nfe-entrada',
            ),
        )
    if len(out) >= MAX_POR_TIPO:
        return out[:MAX_POR_TIPO]
    q_extra = Q()
    if len(q_digits) >= 4:
        q_extra |= Q(chave_acesso__icontains=q_digits)
    restante = MAX_POR_TIPO - len(out)
    hist_qs = filtrar_queryset_por_numeros_documento(
        NFeEntradaHistoricaImportada.objects.select_related('conferencia'),
        q,
        'numero',
        q_extra=q_extra if q_extra else None,
    ).order_by('-dh_emissao')[:restante]
    for h in hist_qs:
        emit = (h.emit_json or {}).get('xNome') or (h.emit_json or {}).get('xFant') or 'Fornecedor'
        url = '/nfe-entrada-historica-importada'
        conf_pk = (
            NFeEntradaConferencia.objects.filter(nf_entrada_historica_id=h.pk)
            .values_list('pk', flat=True)
            .first()
        )
        if conf_pk:
            url = f'/nfe-entrada/{conf_pk}/conferencia'
        out.append(
            _item(
                tipo='nfe_entrada',
                tipo_label='NF-e Entrada',
                titulo=f'NF-e Entrada nº {h.numero}',
                subtitulo=str(emit)[:80],
                url=url,
            ),
        )
    return out


def _subtitulo_titulo(t: TituloFinanceiro) -> str:
    partes = []
    if t.tipo == TituloFinanceiro.Tipo.RECEBER and t.cliente_id:
        partes.append(t.cliente.razao_social)
    elif t.tipo == TituloFinanceiro.Tipo.PAGAR:
        if t.fornecedor_id:
            partes.append(t.fornecedor.razao_social)
        elif t.descricao:
            partes.append(t.descricao)
    saldo = t.valor_aberto if t.valor_aberto is not None else Decimal('0')
    partes.append(f'Saldo: {format_currency_br(saldo)}')
    return ' · '.join(p for p in partes if p)[:120]


def _buscar_titulos(q: str, q_digits: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    out: list[dict[str, str]] = []
    base = TituloFinanceiro.objects.select_related('cliente', 'fornecedor').exclude(
        status=TituloFinanceiro.Status.CANCELADO,
    )
    qs_num = filtrar_queryset_por_numeros_documento(
        base,
        q,
        'numero',
        'origem_numero',
        q_extra=Q(descricao__icontains=q),
    )
    for t in qs_num.filter(tipo=TituloFinanceiro.Tipo.RECEBER).order_by('-data_emissao')[:MAX_POR_TIPO]:
        out.append(
            _item(
                tipo='conta_receber',
                tipo_label='Conta a Receber',
                titulo=t.numero,
                subtitulo=_subtitulo_titulo(t),
                url=f'/financeiro/contas-receber?titulo={t.pk}',
            ),
        )
    for t in qs_num.filter(tipo=TituloFinanceiro.Tipo.PAGAR).order_by('-data_emissao')[:MAX_POR_TIPO]:
        out.append(
            _item(
                tipo='conta_pagar',
                tipo_label='Conta a Pagar',
                titulo=t.numero,
                subtitulo=_subtitulo_titulo(t),
                url=f'/financeiro/contas-pagar?titulo={t.pk}',
            ),
        )
    return out


def _buscar_creditos(q: str) -> list[dict[str, str]]:
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    out = []
    qs = filtrar_queryset_por_numeros_documento(
        CreditoFinanceiro.objects.select_related('cliente', 'fornecedor').filter(cancelado=False),
        q,
        'origem_numero',
        q_extra=Q(motivo__icontains=q) | Q(origem_descricao__icontains=q),
    ).order_by('-data_credito')[:MAX_POR_TIPO]
    for cr in qs:
        titulo = f'Crédito #{cr.pk}'
        if cr.cliente_id:
            sub = f'{cr.cliente.razao_social} · Saldo {format_currency_br(cr.saldo)}'
        elif cr.fornecedor_id:
            sub = f'{cr.fornecedor.razao_social} · Saldo {format_currency_br(cr.saldo)}'
        else:
            sub = f'Saldo {format_currency_br(cr.saldo)}'
        out.append(
            _item(
                tipo='credito',
                tipo_label='Crédito financeiro',
                titulo=titulo,
                subtitulo=sub[:120],
                url='/financeiro/creditos',
            ),
        )
    return out


def _priorizar_exatos(resultados: list[dict[str, str]], q: str) -> list[dict[str, str]]:
    q_lower = q.lower()
    q_digits = _digits(q)

    def score(item: dict[str, str]) -> tuple[int, str]:
        titulo = (item.get('titulo') or '').lower()
        if titulo == q_lower:
            return (0, titulo)
        if q_digits and q_digits in _digits(titulo):
            return (1, titulo)
        if titulo.startswith(q_lower):
            return (2, titulo)
        return (3, titulo)

    return sorted(resultados, key=score)


def executar_busca_global(query: str) -> dict[str, Any]:
    q = (query or '').strip()
    if len(q) < MIN_QUERY_LEN:
        return {'query': q, 'resultados': [], 'mensagem': 'Digite ao menos 2 caracteres.'}

    q_digits = _digits(q)
    resultados: list[dict[str, str]] = []

    # Prioridade: números de documento / CR / CP / NF-e
    if re.match(r'^(CR|CP)-', q, re.I) or q_digits:
        resultados.extend(_buscar_titulos(q, q_digits))
        resultados.extend(_buscar_nfe_saida(q, q_digits))
        resultados.extend(_buscar_nfe_entrada(q, q_digits))

    resultados.extend(_buscar_clientes(q, q_digits))
    resultados.extend(_buscar_fornecedores(q, q_digits))
    resultados.extend(_buscar_produtos(q))
    resultados.extend(_buscar_colaboradores(q))
    resultados.extend(_buscar_empresas(q, q_digits))
    resultados.extend(_buscar_propostas(q))
    resultados.extend(_buscar_pedidos_venda(q))
    resultados.extend(_buscar_pedidos_compra(q))

    if not resultados:
        resultados.extend(_buscar_titulos(q, q_digits))
        resultados.extend(_buscar_nfe_saida(q, q_digits))
        resultados.extend(_buscar_nfe_entrada(q, q_digits))

    resultados.extend(_buscar_creditos(q))

    # Deduplicate by url+titulo
    seen: set[str] = set()
    unicos: list[dict[str, str]] = []
    for r in resultados:
        key = f"{r['tipo']}:{r['url']}:{r['titulo']}"
        if key in seen:
            continue
        seen.add(key)
        unicos.append(r)

    unicos = _priorizar_exatos(unicos, q)[:MAX_TOTAL]
    return {'query': q, 'resultados': unicos}
