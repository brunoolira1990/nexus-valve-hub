"""Geração de PDF do Pedido de Compra — ReportLab + Platypus, layout base `apps.core.pdf`."""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from apps.cadastros.models import Empresa
from apps.core.pdf.base import build_nexus_pdf_bytes, default_page_content_width
from apps.core.pdf.components import (
    build_commercial_order_header,
    build_conditions_commercial_grid,
    build_financial_summary_section,
    build_item_line_table,
    build_observations_block_commercial,
    build_section_title,
    build_supplier_instructions_compact,
    party_block_table,
)
from apps.core.pdf.formatters import (
    dec,
    endereco_cadastro,
    fmt_cnpj,
    fmt_date_br,
    format_phone,
    nobr,
    qty_br,
    txt_or_emdash,
)
from apps.core.pdf.styles import C_BORDER, C_PRIMARY, SPACE_SM, SPACE_XS, base_paragraph_styles

from .comercial_pdf_shared import descricao_pdf_com_linha_ncm, resolver_ncm_item_comercial
from .models import ItemPedidoCompra, PedidoCompra

logger = logging.getLogger(__name__)


def _empresa_compradora_pedido_compra() -> Empresa | None:
    try:
        matriz = Empresa.objects.filter(empresa_pai__isnull=True).order_by('id').first()
        if matriz:
            return matriz
        return Empresa.objects.order_by('id').first()
    except Exception as exc:
        logger.debug('empresa compradora: %s', exc)
        return None


def _logotipo_path_empresa(emp: Empresa | None) -> str | None:
    if not emp:
        return None
    try:
        if emp.logotipo and getattr(emp.logotipo, 'path', None):
            p = emp.logotipo.path
            if p and os.path.isfile(p):
                return p
    except Exception as exc:
        logger.debug('logo empresa id=%s: %s', getattr(emp, 'pk', None), exc)
    return None


def _logotipo_path_fallback() -> str | None:
    try:
        for emp in Empresa.objects.exclude(logotipo='').only('logotipo')[:40]:
            p = _logotipo_path_empresa(emp)
            if p:
                return p
    except Exception as exc:
        logger.debug('logo fallback: %s', exc)
    return None



def _codigo_item(it: ItemPedidoCompra) -> str:
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


def _descricao_base_pc(it: ItemPedidoCompra) -> str:
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


def _desc_item(it: ItemPedidoCompra) -> str:
    ncm = resolver_ncm_item_comercial(
        produto=getattr(it, 'produto', None) if it.produto_id else None,
        snapshot_produto=it.snapshot_produto if isinstance(it.snapshot_produto, dict) else None,
    )
    return descricao_pdf_com_linha_ncm(_descricao_base_pc(it), ncm)


def _endereco_fornecedor(f) -> str:
    return endereco_cadastro(
        f.logradouro or '',
        f.numero or '',
        f.complemento or '',
        f.bairro or '',
        f.cidade or '',
        f.uf or '',
        f.cep or '',
    )


def _endereco_empresa(e: Empresa) -> str:
    return endereco_cadastro(
        e.logradouro or '',
        e.numero or '',
        e.complemento or '',
        e.bairro or '',
        e.cidade or '',
        e.uf or '',
        e.cep or '',
    )


def _condicoes_pagamento_exibicao(pedido: PedidoCompra) -> str:
    dias = list(pedido.dias_parcelas or [])
    if dias:
        return ','.join(str(int(d)) for d in dias)
    return (pedido.condicao_pagamento_texto or '').strip() or '—'


def _parcelas_exibicao(pedido: PedidoCompra) -> str:
    n = int(pedido.quantidade_parcelas or 0)
    if n > 0:
        return str(n)
    v = [x for x in (pedido.vencimentos_previstos or []) if x]
    if v:
        return str(len(v))
    dias = pedido.dias_parcelas or []
    if dias:
        return str(len(dias))
    return '—'


def _vencimentos_exibicao(pedido: PedidoCompra) -> str:
    v = []
    try:
        for d in pedido.vencimentos_previstos or []:
            if d:
                v.append(fmt_date_br(d))
    except Exception:
        pass
    return ' · '.join(v) if v else '—'


def gerar_pedido_compra_pdf_bytes(pedido: PedidoCompra) -> bytes:
    numero_txt = txt_or_emdash(pedido.numero)
    meta_title = f'Pedido de Compra {numero_txt}'

    empresa = _empresa_compradora_pedido_compra()
    logo_path = _logotipo_path_empresa(empresa) or _logotipo_path_fallback()

    _ph, ph_small, ph_right, ph_center, _ph_white = base_paragraph_styles()
    p_party_title = ParagraphStyle(
        'PpT', parent=ph_small, fontName='Helvetica-Bold', fontSize=7.2, leading=9, textColor=C_PRIMARY
    )
    p_party_bold = ParagraphStyle('PpB', parent=ph_small, fontName='Helvetica-Bold', fontSize=8.0, leading=10)
    p_party_norm = ParagraphStyle('PpN', parent=ph_small, fontSize=7.5, leading=9.5)

    def story_builder():
        page_w = default_page_content_width()
        data_s = fmt_date_br(pedido.data)
        st_s = txt_or_emdash(pedido.status)

        emit_rz = (empresa.razao_social or '').strip() or None if empresa else None
        emit_cnpj = None
        if empresa and (empresa.cnpj or '').strip():
            v_cnpj = fmt_cnpj(empresa.cnpj)
            emit_cnpj = None if v_cnpj == '—' else v_cnpj
        emit_end = _endereco_empresa(empresa) if empresa else ''
        emit_end = (emit_end or '').strip()
        emitente_endereco = None if not empresa or emit_end == '—' or not emit_end else emit_end
        emit_tel = (format_phone(empresa.telefone) if empresa else '') or None
        emit_mail = ((empresa.email or '').strip() or None) if empresa else None
        emit_ie = ((empresa.ie or '').strip() or None) if empresa else None
        emit_site = ((empresa.site or '').strip() or None) if empresa else None

        story: list = []
        story.append(
            build_commercial_order_header(
                logo_path=logo_path,
                emitente_razao_social=emit_rz,
                emitente_cnpj=emit_cnpj,
                emitente_ie=emit_ie,
                emitente_endereco=emitente_endereco,
                emitente_telefone=emit_tel,
                emitente_email=emit_mail,
                emitente_site=emit_site,
                document_kind_upper='PEDIDO DE COMPRA',
                numero_nobr_html=nobr(numero_txt),
                meta_line_html=f'Emissão: {nobr(data_s)} · Status: {nobr(st_s)}',
                page_width=page_w,
                ph_small=ph_small,
                ph_center=ph_center,
            )
        )
        story.append(Spacer(1, SPACE_SM))

        f = getattr(pedido, 'fornecedor', None)

        if f is not None:
            tel_f = format_phone(f.telefone, f.celular, f.telefone_alternativo)
            fo_tbl = party_block_table(
                'Fornecedor',
                f.razao_social or '—',
                (f.nome_fantasia or '').strip() or None,
                fmt_cnpj(f.cnpj),
                _endereco_fornecedor(f),
                tel_f,
                (f.email or f.email_nf or None),
                None,
                page_w,
                p_title=p_party_title,
                p_bold=p_party_bold,
                p_norm=p_party_norm,
                compact=True,
            )
        else:
            fo_tbl = Table([[Paragraph('Fornecedor não vinculado.', p_party_norm)]], colWidths=[page_w])
            fo_tbl.setStyle(
                TableStyle(
                    [
                        ('BOX', (0, 0), (-1, -1), 0.45, C_BORDER),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ]
                )
            )

        story.append(fo_tbl)
        story.append(Spacer(1, 1.35 * mm))

        cond_rows = [
            ('Pagamento:', _condicoes_pagamento_exibicao(pedido)),
            ('Parcelas:', _parcelas_exibicao(pedido)),
            ('Vencimentos:', _vencimentos_exibicao(pedido)),
            ('Prazo de entrega:', (pedido.prazo_entrega_texto or '').strip() or '—'),
            ('Data prevista:', fmt_date_br(pedido.data_prevista_entrega)),
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
        story.append(Spacer(1, 1.15 * mm))

        story.append(build_section_title('Itens do pedido', ph_small=ph_small, compact=True, page_w=page_w))
        story.append(Spacer(1, 0.95 * mm))

        itens = list(pedido.itens.select_related('produto').all())
        subtotal = Decimal('0')
        total_desc = Decimal('0')
        total_ipi = Decimal('0')
        total_st = Decimal('0')
        total_frete = Decimal('0')
        total_outras = Decimal('0')

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
            subtotal += dec(it.valor_produtos)
            total_desc += dec(it.desconto_valor)
            total_ipi += dec(it.ipi_valor)
            total_st += dec(it.icms_st_valor)
            total_frete += dec(it.frete_valor)
            total_outras += dec(it.outras_despesas_valor)
            pu = dec(it.preco_por_unidade_negociada or it.valor_unitario)
            q_raw = qty_br(it.quantidade_negociada or it.quantidade)
            un = (it.unidade_negociada or '').strip().upper()[:16] or '—'
            story.append(
                KeepTogether(
                    [
                        build_item_line_table(
                            codigo=_codigo_item(it),
                            descricao=_desc_item(it),
                            descricao_markup=True,
                            unidade=un,
                            qtd_txt=q_raw,
                            valor_unit=pu,
                            valor_produtos=dec(it.valor_produtos),
                            desconto=dec(it.desconto_valor),
                            ipi=dec(it.ipi_valor),
                            icms_st=dec(it.icms_st_valor),
                            total=dec(it.valor_total_item),
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
                frete=total_frete,
                outras_despesas=total_outras,
                ipi=total_ipi,
                icms_st=total_st,
                valor_total_final=dec(pedido.valor_total),
                ph_small=ph_small,
                ph_right=ph_right,
                compact=True,
            )
        )
        story.append(Spacer(1, 1.1 * mm))
        story.extend(build_supplier_instructions_compact(page_w=page_w, ph_small=ph_small))
        story.append(Spacer(1, 0.95 * mm))
        story.extend(
            build_observations_block_commercial(
                texto=getattr(pedido, 'observacoes', None),
                page_w=page_w,
                ph_small=ph_small,
                compact_empty=True,
            )
        )
        return story

    return build_nexus_pdf_bytes(
        meta_title=meta_title,
        meta_subject='Pedido de Compra',
        story_builder=story_builder,
        footer_document_kind='Pedido de Compra',
        footer_usage_tag='uso comercial',
    )
