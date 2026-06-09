"""Geração de PDF comercial do Pedido de Venda — ReportLab + layout `apps.core.pdf`.

Documento para envio ao cliente: pedido, condições, itens e totais.
Dados fiscais da NF-e (DANFE, XML, homologação, cStat etc.) ficam no ERP (aba NF-e / Fiscal).
Futuro opcional: «PDF interno do pedido com dados fiscais» — não implementado nesta fase.
"""

from __future__ import annotations

from decimal import Decimal

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from apps.core.pdf.base import build_nexus_pdf_bytes, default_page_content_width
from apps.core.pdf.components import (
    build_commercial_order_header,
    build_conditions_commercial_grid,
    build_financial_summary_section,
    build_item_line_table,
    build_observations_block_commercial,
    build_section_title,
    party_block_table,
)
from apps.core.pdf.formatters import (
    dec,
    fmt_cnpj,
    fmt_date_br,
    format_phone,
    format_currency_br,
    nobr,
    qty_br,
    txt_or_emdash,
)
from apps.core.pdf.styles import C_BORDER, C_MUTED, C_PRIMARY, SPACE_SM, SPACE_XS, base_paragraph_styles

from .comercial_pdf_shared import (
    descricao_pdf_com_linha_ncm,
    endereco_cliente,
    endereco_empresa,
    logotipo_path_empresa,
    logotipo_path_fallback,
    nome_vendedor,
    parcelas_exibicao,
    prazo_entrega_exibicao_pedido,
    resolver_ncm_item_comercial,
    vencimentos_exibicao,
)
from .faturamento_pedido_venda import (
    montar_resumo_faturamento,
    quantidade_pendente_item,
    quantidade_pedida_item,
    preco_unitario_item,
)
from .models import ItemPedidoVenda, PedidoVenda
from .pedido_venda_apresentacao import (
    condicao_pagamento_pdf_amigavel,
    label_status_pedido,
    prazo_entrega_pdf_amigavel,
)
from .pedido_venda_totais import calcular_totais_pedido_venda


def _codigo_item_pv(it: ItemPedidoVenda) -> str:
    try:
        if it.produto_id and it.produto and (it.produto.codigo_completo or '').strip():
            return (it.produto.codigo_completo or '').strip()
    except Exception:
        pass
    snap = it.snapshot_produto or {}
    if isinstance(snap, dict):
        for k in ('codigo_completo', 'codigo', 'sku'):
            v = snap.get(k)
            if v and str(v).strip():
                return str(v).strip()
    return '—'


def _descricao_base_pv(it: ItemPedidoVenda) -> str:
    try:
        if it.produto_id and it.produto and (it.produto.descricao or '').strip():
            return (it.produto.descricao or '').strip()
    except Exception:
        pass
    snap = it.snapshot_produto or {}
    if isinstance(snap, dict):
        d = snap.get('descricao')
        if d and str(d).strip():
            return str(d).strip()
    return '—'


def _desc_item_pv(it: ItemPedidoVenda) -> str:
    snap_fiscal = it.snapshot_fiscal if isinstance(it.snapshot_fiscal, dict) else None
    snap_prod = it.snapshot_produto if isinstance(it.snapshot_produto, dict) else None
    ncm = resolver_ncm_item_comercial(
        produto=getattr(it, 'produto', None) if it.produto_id else None,
        snapshot_produto=snap_prod,
        snapshot_fiscal=snap_fiscal,
    )
    return descricao_pdf_com_linha_ncm(_descricao_base_pv(it), ncm)


def _total_linha_pv(it: ItemPedidoVenda) -> Decimal:
    q = quantidade_pedida_item(it)
    p = preco_unitario_item(it)
    d = dec(it.desconto)
    return max(Decimal('0'), q * p - d)


def _linha_faturamento_item(it: ItemPedidoVenda, ph_small: ParagraphStyle, page_w: float) -> Table:
    q_ped = quantidade_pedida_item(it)
    q_fat = dec(it.quantidade_faturada)
    q_pend = quantidade_pendente_item(it)
    from .pedido_venda_apresentacao import label_status_item

    st = label_status_item(it.status_item or 'PENDENTE')
    txt = (
        f'Qtd. pedida: {qty_br(q_ped)} · Faturada: {qty_br(q_fat)} · '
        f'Pendente: {qty_br(q_pend)} · Status: {st}'
    )
    p = ParagraphStyle('PvFat', parent=ph_small, fontSize=6.6, leading=8, textColor=C_MUTED)
    tbl = Table([[Paragraph(txt, p)]], colWidths=[page_w])
    tbl.setStyle(
        TableStyle(
            [
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tbl


def gerar_pedido_venda_pdf_bytes(pedido: PedidoVenda) -> bytes:
    numero_txt = txt_or_emdash(pedido.numero)
    meta_title = f'Pedido de Venda {numero_txt}'

    empresa = getattr(pedido, 'empresa_emitente', None)
    logo_path = logotipo_path_empresa(empresa) or logotipo_path_fallback()

    resumo_fat = montar_resumo_faturamento(pedido)
    totais = calcular_totais_pedido_venda(pedido)

    _ph, ph_small, ph_right, ph_center, _ph_white = base_paragraph_styles()
    p_party_title = ParagraphStyle(
        'PvT', parent=ph_small, fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=C_PRIMARY
    )
    p_party_bold = ParagraphStyle('PvB', parent=ph_small, fontName='Helvetica-Bold', fontSize=8.0, leading=10)
    p_party_norm = ParagraphStyle('PvN', parent=ph_small, fontSize=7.5, leading=9.5)

    def story_builder():
        page_w = default_page_content_width()
        data_s = fmt_date_br(pedido.data)
        st_s = label_status_pedido(pedido.status)

        emit_rz = (empresa.razao_social or '').strip() or None if empresa else None
        emit_cnpj = None
        if empresa and (empresa.cnpj or '').strip():
            v_cnpj = fmt_cnpj(empresa.cnpj)
            emit_cnpj = None if v_cnpj == '—' else v_cnpj
        emit_end = endereco_empresa(empresa) if empresa else ''
        emit_end = (emit_end or '').strip()
        emitente_endereco = None if not empresa or emit_end == '—' or not emit_end else emit_end

        story: list = []
        story.append(
            build_commercial_order_header(
                logo_path=logo_path,
                emitente_razao_social=emit_rz,
                emitente_cnpj=emit_cnpj,
                emitente_ie=((empresa.ie or '').strip() or None) if empresa else None,
                emitente_endereco=emitente_endereco,
                emitente_telefone=(format_phone(empresa.telefone) if empresa else '') or None,
                emitente_email=((empresa.email or '').strip() or None) if empresa else None,
                emitente_site=((empresa.site or '').strip() or None) if empresa else None,
                document_kind_upper='PEDIDO DE VENDA',
                numero_nobr_html=nobr(numero_txt),
                meta_line_html=f'Emissão: {nobr(data_s)} · Status: {nobr(st_s)}',
                page_width=page_w,
                ph_small=ph_small,
                ph_center=ph_center,
            )
        )
        story.append(Spacer(1, SPACE_SM))

        cli = getattr(pedido, 'cliente', None)
        if cli is not None:
            cli_tbl = party_block_table(
                'Cliente',
                cli.razao_social or '—',
                (cli.nome_fantasia or '').strip() or None,
                fmt_cnpj(cli.cnpj),
                endereco_cliente(cli),
                format_phone(cli.telefone, getattr(cli, 'celular', None)),
                (cli.email or None),
                None,
                page_w,
                p_title=p_party_title,
                p_bold=p_party_bold,
                p_norm=p_party_norm,
                compact=True,
            )
        else:
            cli_tbl = Table([[Paragraph('Cliente não vinculado.', p_party_norm)]], colWidths=[page_w])
            cli_tbl.setStyle(
                TableStyle(
                    [
                        ('BOX', (0, 0), (-1, -1), 0.45, C_BORDER),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ]
                )
            )
        story.append(cli_tbl)
        story.append(Spacer(1, 1.35 * mm))

        vend_nome = nome_vendedor(vendedor_ref=getattr(pedido, 'vendedor_ref', None), vendedor_texto=pedido.vendedor)
        origem = '—'
        try:
            if pedido.proposta_id and pedido.proposta:
                origem = f'Proposta {pedido.proposta.numero or pedido.proposta_id}'
        except Exception:
            if pedido.proposta_id:
                origem = f'Proposta #{pedido.proposta_id}'

        meta_rows = [
            ('Vendedor:', vend_nome),
            ('Origem:', origem),
        ]
        meta_tbl_data = [[Paragraph(f'<b>{k}</b> {nobr(v)}', p_party_norm)] for k, v in meta_rows]
        meta_tbl = Table(meta_tbl_data, colWidths=[page_w])
        meta_tbl.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.45, C_BORDER),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(meta_tbl)
        story.append(Spacer(1, 1.15 * mm))

        vencs = list(pedido.vencimentos_previstos or [])
        venc_label = 'Vencimento:' if len(vencs) == 1 else 'Vencimentos:'
        cond_rows = [
            (
                'Pagamento:',
                condicao_pagamento_pdf_amigavel(
                    pedido.condicao_pagamento_texto or '',
                    list(pedido.dias_parcelas or []),
                ),
            ),
            ('Parcelas:', parcelas_exibicao(
                quantidade_parcelas=pedido.quantidade_parcelas,
                vencimentos_previstos=vencs,
                dias_parcelas=list(pedido.dias_parcelas or []),
            )),
            (venc_label, vencimentos_exibicao(vencs)),
            ('Prazo previsto de entrega:', prazo_entrega_pdf_amigavel(prazo_entrega_exibicao_pedido(pedido))),
        ]
        story.extend(
            build_conditions_commercial_grid(
                'Condições comerciais',
                cond_rows,
                page_w=page_w,
                ph_small=ph_small,
                pairs_per_row=2,
                label_width_frac=0.31,
            )
        )
        story.append(Spacer(1, 1.0 * mm))

        fat_rows = [
            ('Valor total pedido:', format_currency_br(totais.valor_total)),
            ('Valor faturado:', format_currency_br(dec(resumo_fat.get('valor_faturado')))),
            ('Valor pendente:', format_currency_br(
                max(Decimal('0'), totais.valor_total - dec(resumo_fat.get('valor_faturado')))
            )),
            ('Status faturamento:', label_status_pedido(resumo_fat.get('status'))),
        ]
        story.extend(
            build_conditions_commercial_grid(
                'Resumo de faturamento',
                fat_rows,
                page_w=page_w,
                ph_small=ph_small,
                pairs_per_row=2,
                label_width_frac=0.35,
            )
        )

        story.append(Spacer(1, 1.15 * mm))
        story.append(build_section_title('Itens do pedido', ph_small=ph_small, compact=True, page_w=page_w))
        story.append(Spacer(1, 0.95 * mm))

        itens = list(pedido.itens.select_related('produto').order_by('id'))
        totais_itens = calcular_totais_pedido_venda(pedido, itens=itens)
        subtotal = totais_itens.subtotal_produtos
        total_desc = totais_itens.desconto_total

        if not itens:
            story.append(
                build_item_line_table(
                    codigo='—',
                    descricao='Nenhum item.',
                    unidade='—',
                    qtd_txt='0',
                    valor_unit=Decimal('0'),
                    valor_produtos=Decimal('0'),
                    desconto=Decimal('0'),
                    ipi=Decimal('0'),
                    icms_st=Decimal('0'),
                    total=Decimal('0'),
                    page_w=page_w,
                    ph_small=ph_small,
                )
            )
        for idx, it in enumerate(itens):
            if idx:
                story.append(Spacer(1, SPACE_XS))
            linha_total = _total_linha_pv(it)
            q_raw = quantidade_pedida_item(it)
            pu = preco_unitario_item(it)
            desc_v = dec(it.desconto)
            vp = q_raw * pu
            un = (it.unidade_negociada or '').strip().upper()[:16] or '—'
            bloco = [
                build_item_line_table(
                    codigo=_codigo_item_pv(it),
                    descricao=_desc_item_pv(it),
                    descricao_markup=True,
                    unidade=un,
                    qtd_txt=qty_br(q_raw),
                    valor_unit=pu,
                    valor_produtos=vp,
                    desconto=desc_v,
                    ipi=Decimal('0'),
                    icms_st=Decimal('0'),
                    total=linha_total,
                    page_w=page_w,
                    ph_small=ph_small,
                ),
                _linha_faturamento_item(it, ph_small, page_w),
            ]
            story.append(KeepTogether(bloco))

        story.append(Spacer(1, 1.2 * mm))
        story.extend(
            build_financial_summary_section(
                page_w=page_w,
                subtotal_produtos=subtotal,
                desconto_total=total_desc,
                frete=totais_itens.frete,
                outras_despesas=totais_itens.outras_despesas,
                ipi=totais_itens.ipi,
                icms_st=totais_itens.icms_st,
                valor_total_final=totais_itens.valor_total,
                ph_small=ph_small,
                ph_right=ph_right,
                compact=True,
            )
        )

        obs_parts = []
        com = (pedido.observacoes_comerciais or '').strip()
        intern = (pedido.observacoes_internas or '').strip()
        if com:
            obs_parts.append(f'Comercial: {com}')
        if intern:
            obs_parts.append(f'Internas: {intern}')
        obs_txt = '\n'.join(obs_parts) if obs_parts else None

        story.append(Spacer(1, 0.95 * mm))
        story.extend(
            build_observations_block_commercial(
                texto=obs_txt,
                page_w=page_w,
                ph_small=ph_small,
                compact_empty=True,
            )
        )
        return story

    return build_nexus_pdf_bytes(
        meta_title=meta_title,
        meta_subject='Pedido de Venda',
        story_builder=story_builder,
        footer_document_kind='Pedido de Venda',
        footer_usage_tag='uso comercial',
    )
