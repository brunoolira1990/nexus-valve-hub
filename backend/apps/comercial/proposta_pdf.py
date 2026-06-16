"""Geração de PDF da Proposta Comercial — ReportLab + layout `apps.core.pdf`."""

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
    build_section_title,
    party_block_table,
)
from apps.core.pdf.formatters import (
    dec,
    fmt_cnpj,
    fmt_date_br,
    format_phone,
    nobr,
    qty_br,
    txt_or_emdash,
)
from apps.core.pdf.styles import C_BORDER, C_PRIMARY, SPACE_SM, SPACE_XS, base_paragraph_styles

from .comercial_pdf_shared import (
    condicao_pagamento_proposta_pdf,
    descricao_pdf_com_linha_ncm,
    endereco_cliente,
    endereco_empresa,
    logotipo_path_empresa,
    logotipo_path_fallback,
    nome_vendedor,
    parcelas_exibicao,
    prazo_entrega_exibicao_proposta,
    resolver_ncm_item_comercial,
    validade_proposta_pdf,
    vencimentos_exibicao,
)
from .models import ItemProposta, Proposta


def _codigo_item_proposta(it: ItemProposta) -> str:
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


def _descricao_base_proposta(it: ItemProposta) -> str:
    avulsa = (it.descricao_avulsa or '').strip()
    if avulsa:
        return avulsa
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


def _desc_item_proposta(it: ItemProposta) -> str:
    ncm = resolver_ncm_item_comercial(
        produto=getattr(it, 'produto', None) if it.produto_id else None,
        snapshot_produto=it.snapshot_produto if isinstance(it.snapshot_produto, dict) else None,
        ncm_avulso=it.ncm_avulso,
    )
    return descricao_pdf_com_linha_ncm(_descricao_base_proposta(it), ncm)


def _total_linha_proposta(it: ItemProposta) -> Decimal:
    q = dec(it.quantidade_negociada or it.quantidade)
    p = dec(it.preco_por_unidade_negociada or it.preco_final or it.valor_unitario)
    d = dec(it.desconto)
    return max(Decimal('0'), q * p - d)


def _bloco_cliente_proposta(proposta: Proposta, *, page_w, p_party_title, p_party_bold, p_party_norm):
    ref_cli = (proposta.referencia_cliente or '').strip()
    ref_linha = f'Ref. requisição/cotação: {ref_cli}' if ref_cli else None

    cli = getattr(proposta, 'cliente', None)
    if cli is not None:
        fantasia = (cli.nome_fantasia or '').strip() or None
        if ref_linha:
            fantasia = f'{ref_linha}' + (f' · {fantasia}' if fantasia else '')
        return party_block_table(
            'Cliente',
            cli.razao_social or '—',
            fantasia,
            fmt_cnpj(cli.cnpj),
            endereco_cliente(cli),
            format_phone(cli.telefone, cli.celular),
            (cli.email or None),
            None,
            page_w,
            p_title=p_party_title,
            p_bold=p_party_bold,
            p_norm=p_party_norm,
            compact=True,
        )

    nome_av = (proposta.cliente_avulso_nome or '').strip() or '—'
    uf = (proposta.uf_destino_avulso or '').strip()
    endereco_av = f'UF destino: {uf}' if uf else '—'
    return party_block_table(
        'Cliente',
        nome_av,
        ref_linha,
        '—',
        endereco_av,
        None,
        None,
        None,
        page_w,
        p_title=p_party_title,
        p_bold=p_party_bold,
        p_norm=p_party_norm,
        compact=True,
    )


def gerar_proposta_pdf_bytes(proposta: Proposta) -> bytes:
    numero_txt = txt_or_emdash(proposta.numero)
    meta_title = f'Proposta Comercial {numero_txt}'

    empresa = getattr(proposta, 'empresa_emitente', None)
    logo_path = logotipo_path_empresa(empresa) or logotipo_path_fallback()

    _ph, ph_small, ph_right, ph_center, _ph_white = base_paragraph_styles()
    p_party_title = ParagraphStyle(
        'PrT', parent=ph_small, fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=C_PRIMARY
    )
    p_party_bold = ParagraphStyle('PrB', parent=ph_small, fontName='Helvetica-Bold', fontSize=8.0, leading=10)
    p_party_norm = ParagraphStyle('PrN', parent=ph_small, fontSize=7.5, leading=9.5)

    def story_builder():
        page_w = default_page_content_width()
        data_s = fmt_date_br(proposta.data)
        val_exibicao = validade_proposta_pdf(
            data=proposta.data,
            validade=proposta.validade,
            validade_dias=proposta.validade_dias,
        )

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
                document_kind_upper='PROPOSTA COMERCIAL',
                numero_nobr_html=nobr(numero_txt),
                meta_line_html=f'Emissão: {nobr(data_s)}',
                page_width=page_w,
                ph_small=ph_small,
                ph_center=ph_center,
            )
        )
        story.append(Spacer(1, SPACE_SM))

        story.append(
            _bloco_cliente_proposta(
                proposta,
                page_w=page_w,
                p_party_title=p_party_title,
                p_party_bold=p_party_bold,
                p_party_norm=p_party_norm,
            )
        )
        story.append(Spacer(1, 1.35 * mm))

        vend_nome = nome_vendedor(vendedor_ref=getattr(proposta, 'vendedor_ref', None), vendedor_texto=proposta.vendedor)
        vend_tbl = Table(
            [[Paragraph(f'<b>Vendedor:</b> {nobr(vend_nome)}', p_party_norm)]],
            colWidths=[page_w],
        )
        vend_tbl.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.45, C_BORDER),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(vend_tbl)
        story.append(Spacer(1, 1.15 * mm))

        story.append(build_section_title('Itens da proposta', ph_small=ph_small, compact=True, page_w=page_w))
        story.append(Spacer(1, 0.95 * mm))

        itens = list(proposta.itens.select_related('produto').all())
        subtotal = Decimal('0')
        total_desc = Decimal('0')

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
            linha_total = _total_linha_proposta(it)
            q_raw = dec(it.quantidade_negociada or it.quantidade)
            pu = dec(it.preco_por_unidade_negociada or it.preco_final or it.valor_unitario)
            desc_v = dec(it.desconto)
            vp = q_raw * pu
            subtotal += vp
            total_desc += desc_v
            un = (it.unidade_negociada or '').strip().upper()[:16] or '—'
            story.append(
                KeepTogether(
                    [
                        build_item_line_table(
                            codigo=_codigo_item_proposta(it),
                            descricao=_desc_item_proposta(it),
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
                        )
                    ]
                )
            )

        story.append(Spacer(1, 1.2 * mm))
        story.extend(
            build_financial_summary_section(
                page_w=page_w,
                subtotal_produtos=subtotal,
                desconto_total=total_desc,
                frete=Decimal('0'),
                outras_despesas=Decimal('0'),
                ipi=Decimal('0'),
                icms_st=Decimal('0'),
                valor_total_final=dec(proposta.valor_total),
                ph_small=ph_small,
                ph_right=ph_right,
                compact=True,
            )
        )
        story.append(Spacer(1, 1.15 * mm))

        cond_rows = [
            (
                'Condição de pagamento:',
                condicao_pagamento_proposta_pdf(
                    condicao_texto=proposta.condicao_pagamento_texto,
                    dias_parcelas=list(proposta.dias_parcelas or []),
                ),
            ),
            ('Prazo de entrega:', prazo_entrega_exibicao_proposta(proposta)),
            ('Validade:', val_exibicao),
            ('Parcelas:', parcelas_exibicao(
                quantidade_parcelas=proposta.quantidade_parcelas,
                vencimentos_previstos=list(proposta.vencimentos_previstos or []),
                dias_parcelas=list(proposta.dias_parcelas or []),
            )),
            ('Vencimentos:', vencimentos_exibicao(list(proposta.vencimentos_previstos or []))),
        ]
        frete_txt = (proposta.frete_texto or '').strip()
        if frete_txt:
            cond_rows.insert(2, ('Frete:', frete_txt))
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
        story.append(Spacer(1, 1.15 * mm))

        obs = (proposta.observacoes_proposta or '').strip()
        if obs:
            story.append(build_section_title('Observações', ph_small=ph_small, compact=True, page_w=page_w))
            story.append(Spacer(1, 0.6 * mm))
            story.append(Paragraph(obs.replace('\n', '<br/>'), p_party_norm))
            story.append(Spacer(1, 1.0 * mm))

        msg = (proposta.mensagem_comercial or '').strip()
        if msg:
            story.append(build_section_title('Mensagem comercial', ph_small=ph_small, compact=True, page_w=page_w))
            story.append(Spacer(1, 0.6 * mm))
            story.append(Paragraph(msg.replace('\n', '<br/>'), p_party_norm))
            story.append(Spacer(1, 1.0 * mm))

        return story

    return build_nexus_pdf_bytes(
        meta_title=meta_title,
        meta_subject='Proposta Comercial',
        story_builder=story_builder,
        footer_document_kind='Proposta Comercial',
        footer_usage_tag='uso comercial',
    )
