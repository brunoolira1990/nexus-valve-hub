"""Geração de PDF comercial do Pedido de Venda — ReportLab + layout `apps.core.pdf`.

Documento para envio ao cliente: pedido, condições, itens e totais.
Dados fiscais da NF-e (DANFE, XML, homologação, cStat etc.) ficam no ERP (aba NF-e / Fiscal).
Futuro opcional: «PDF interno do pedido com dados fiscais» — não implementado nesta fase.
"""

from __future__ import annotations

from decimal import Decimal

from xml.sax.saxutils import escape

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
    build_pedido_venda_items_batch_table,
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
from apps.core.pdf.styles import C_BORDER, C_PRIMARY, base_paragraph_styles

from .comercial_pdf_shared import (
    NCM_NAO_INFORMADO,
    descricao_pdf_com_linha_ncm,
    endereco_cliente,
    endereco_empresa,
    logotipo_path_empresa,
    logotipo_path_fallback,
    nome_vendedor,
    prazo_entrega_exibicao_pedido,
    resolver_ncm_item_comercial,
    vencimentos_exibicao,
)
from .faturamento_pedido_venda import (
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

_LAYOUT_DEZ_ITENS_MAX = 10
_OBS_LONGA_LIMITE_CHARS = 200


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
    total = q * p - d
    if total < 0:
        raise ValueError(f'Item do pedido #{it.pk} possui desconto maior que o subtotal.')
    return total


def _nota_faturamento_item(it: ItemPedidoVenda, *, abreviada: bool = False) -> str:
    q_ped = quantidade_pedida_item(it)
    q_fat = dec(it.quantidade_faturada)
    q_pend = quantidade_pendente_item(it)
    from .pedido_venda_apresentacao import label_status_item

    st = label_status_item(it.status_item or 'PENDENTE')
    if abreviada:
        return f'Ped:{qty_br(q_ped)} Fat:{qty_br(q_fat)} Pend:{qty_br(q_pend)} · {st}'
    return (
        f'Qtd. pedida: {qty_br(q_ped)} · Faturada: {qty_br(q_fat)} · '
        f'Pendente: {qty_br(q_pend)} · Status: {st}'
    )


def _bloco_descricao_item_compact(it: ItemPedidoVenda, nota: str) -> str:
    """Descrição em destaque + metadados (NCM, código, faturamento) em linha secundária única."""
    snap_fiscal = it.snapshot_fiscal if isinstance(it.snapshot_fiscal, dict) else None
    snap_prod = it.snapshot_produto if isinstance(it.snapshot_produto, dict) else None
    ncm = resolver_ncm_item_comercial(
        produto=getattr(it, 'produto', None) if it.produto_id else None,
        snapshot_produto=snap_prod,
        snapshot_fiscal=snap_fiscal,
    )
    desc_safe = escape(_descricao_base_pv(it).strip() or '—')
    cod_safe = escape(_codigo_item_pv(it))
    ncm_safe = escape((ncm or '').strip() or NCM_NAO_INFORMADO)
    nota_safe = escape(nota)
    return (
        f'{desc_safe}<br/>'
        f'<font size="6.5" color="#64748b">'
        f'NCM: {ncm_safe} · Cód. {cod_safe} · {nota_safe}'
        f'</font>'
    )


def _validade_exibicao_pedido(pedido: PedidoVenda) -> str:
    try:
        if pedido.proposta_id and pedido.proposta and pedido.proposta.validade:
            return fmt_date_br(pedido.proposta.validade)
    except Exception:
        pass
    vencs = list(pedido.vencimentos_previstos or [])
    txt = vencimentos_exibicao(vencs)
    return txt if txt and txt != '—' else '—'


def _frete_condicoes_pedido(pedido: PedidoVenda, frete_valor) -> str | None:
    try:
        if pedido.proposta_id and pedido.proposta:
            ft = (pedido.proposta.frete_texto or '').strip()
            if ft:
                return ft
    except Exception:
        pass
    return None


def _linhas_condicoes_comerciais_pdf(
    pedido: PedidoVenda,
    *,
    vend_nome: str,
    frete_valor,
) -> list[tuple[str, str]]:
    """Campos essenciais no PDF — demais dados permanecem no ERP e no resumo financeiro."""
    rows: list[tuple[str, str]] = [
        ('Vendedor:', vend_nome),
        ('Validade:', _validade_exibicao_pedido(pedido)),
        (
            'Forma de pagamento:',
            condicao_pagamento_pdf_amigavel(
                pedido.condicao_pagamento_texto or '',
                list(pedido.dias_parcelas or []),
            ),
        ),
        (
            'Prazo de entrega:',
            prazo_entrega_pdf_amigavel(prazo_entrega_exibicao_pedido(pedido)),
        ),
    ]
    st = label_status_pedido(pedido.status)
    if st and st.strip() and st != '—':
        rows.append(('Status:', st))
    frete_txt = _frete_condicoes_pedido(pedido, frete_valor)
    if frete_txt:
        rows.append(('Condição de frete:', frete_txt))
    return rows


def gerar_pedido_venda_pdf_bytes(pedido: PedidoVenda) -> bytes:
    numero_txt = txt_or_emdash(pedido.numero)
    meta_title = f'Pedido de Venda {numero_txt}'

    empresa = getattr(pedido, 'empresa_emitente', None)
    logo_path = logotipo_path_empresa(empresa) or logotipo_path_fallback()

    _ph, ph_small, ph_right, ph_center, _ph_white = base_paragraph_styles()

    def story_builder():
        page_w = default_page_content_width()
        data_s = fmt_date_br(pedido.data)
        st_s = label_status_pedido(pedido.status)

        com_obs = (pedido.observacoes_comerciais or '').strip()
        intern_obs = (pedido.observacoes_internas or '').strip()
        obs_longa = len(com_obs) + len(intern_obs) >= _OBS_LONGA_LIMITE_CHARS

        itens = list(pedido.itens.select_related('produto').order_by('id'))
        layout_dez_itens = len(itens) <= _LAYOUT_DEZ_ITENS_MAX and not obs_longa
        layout_denso = layout_dez_itens and len(itens) >= 7
        usar_tabela_lote = len(itens) > 1 and not obs_longa

        party_fs_title = 6.9 if layout_denso else 7.2
        party_fs_bold = 7.6 if layout_denso else 8.0
        party_fs_norm = 7.0 if layout_denso else 7.5
        p_party_title = ParagraphStyle(
            'PvT', parent=ph_small, fontName='Helvetica-Bold', fontSize=party_fs_title, leading=8.6, textColor=C_PRIMARY
        )
        p_party_bold = ParagraphStyle(
            'PvB', parent=ph_small, fontName='Helvetica-Bold', fontSize=party_fs_bold, leading=9.2
        )
        p_party_norm = ParagraphStyle('PvN', parent=ph_small, fontSize=party_fs_norm, leading=8.8)

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
                compact=layout_denso,
            )
        )
        story.append(Spacer(1, 0.95 * mm if layout_dez_itens and not layout_denso else (0.85 * mm if layout_denso else 1.2 * mm)))

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
        story.append(Spacer(1, 0.75 * mm if layout_dez_itens and not layout_denso else (0.65 * mm if layout_denso else 0.85 * mm)))

        vend_nome = nome_vendedor(vendedor_ref=getattr(pedido, 'vendedor_ref', None), vendedor_texto=pedido.vendedor)

        totais_itens = calcular_totais_pedido_venda(pedido, itens=itens)
        cond_rows = _linhas_condicoes_comerciais_pdf(
            pedido,
            vend_nome=vend_nome,
            frete_valor=totais_itens.frete,
        )
        story.extend(
            build_conditions_commercial_grid(
                'Condições comerciais',
                cond_rows,
                page_w=page_w,
                ph_small=ph_small,
                pairs_per_row=2 if layout_dez_itens else 3,
                label_width_frac=0.32,
                tight=layout_denso,
            )
        )

        story.append(Spacer(1, 0.65 * mm if layout_dez_itens else 0.75 * mm))
        story.append(build_section_title('Itens do pedido', ph_small=ph_small, compact=True, page_w=page_w))
        story.append(Spacer(1, 0.45 * mm if usar_tabela_lote else (0.5 * mm if layout_dez_itens else 0.55 * mm)))

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
        elif usar_tabela_lote:
            linhas_lote = []
            for it in itens:
                q_raw = quantidade_pedida_item(it)
                pu = preco_unitario_item(it)
                desc_v = dec(it.desconto)
                nota = _nota_faturamento_item(it, abreviada=layout_dez_itens)
                linhas_lote.append(
                    {
                        'codigo': _codigo_item_pv(it),
                        'descricao': (
                            _bloco_descricao_item_compact(it, nota)
                            if layout_dez_itens
                            else _desc_item_pv(it)
                        ),
                        'descricao_markup': True,
                        'unidade': (it.unidade_negociada or '').strip().upper()[:16] or '—',
                        'qtd_txt': qty_br(q_raw),
                        'valor_unit': pu,
                        'valor_produtos': q_raw * pu,
                        'desconto': desc_v,
                        'ipi': Decimal('0'),
                        'icms_st': Decimal('0'),
                        'total': _total_linha_pv(it),
                        'nota_rodape': nota if not layout_dez_itens else '',
                    }
                )
            story.append(
                build_pedido_venda_items_batch_table(
                    page_w=page_w,
                    ph_small=ph_small,
                    linhas=linhas_lote,
                    readable_compact=layout_dez_itens,
                    descricao_largura_total=layout_dez_itens,
                )
            )
        else:
            for idx, it in enumerate(itens):
                if idx:
                    story.append(Spacer(1, 0.65 * mm))
                linha_total = _total_linha_pv(it)
                q_raw = quantidade_pedida_item(it)
                pu = preco_unitario_item(it)
                desc_v = dec(it.desconto)
                vp = q_raw * pu
                un = (it.unidade_negociada or '').strip().upper()[:16] or '—'
                story.append(
                    KeepTogether(
                        [
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
                                nota_rodape=_nota_faturamento_item(it),
                                dense=True,
                            ),
                        ]
                    )
                )

        story.append(Spacer(1, 0.5 * mm if layout_dez_itens else 0.75 * mm))
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
                tight=layout_denso,
                ultra_compact=layout_dez_itens,
                full_width=True,
            )
        )

        obs_parts = []
        if com_obs:
            obs_parts.append(f'Comercial: {com_obs}')
        if intern_obs:
            obs_parts.append(f'Internas: {intern_obs}')
        obs_txt = '\n'.join(obs_parts) if obs_parts else None

        story.append(Spacer(1, 0.35 * mm if layout_dez_itens else 0.55 * mm))
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
