"""
DANFE BFR — quadro Cálculo do Imposto: rótulo «VALOR TOTAL DOS PRODUTOS» em duas linhas.

A biblioteca usa uma única linha na célula estreita e corta o «S» final.
"""

from __future__ import annotations

from fpdf.enums import MethodReturnValue

from brazilfiscalreport.danfe.danfe import extract_text, format_number
from brazilfiscalreport.danfe.danfe_basic_field import DanfeBasicField
from brazilfiscalreport.danfe.danfe_block import DanfeBlock
from brazilfiscalreport.danfe.danfe_conf import DEFAULT_FIELD_HEIGHT, DEFAULT_HEIGHT_FONT_CONTENT
from brazilfiscalreport.danfe.models import BaseFieldInfo

from apps.fiscal.danfe_conferencia_layout import IMPOSTO_LABELS_DISPLAY

LABEL_VALOR_TOTAL_PRODUTOS = IMPOSTO_LABELS_DISPLAY['imp_valor_produtos']


class NexusDanfeBasicField(DanfeBasicField):
    """Rótulo com quebra de linha quando a descrição contém \\n; valor no rodapé da célula."""

    def render(self):
        from brazilfiscalreport.pdf_element import Element

        Element.render(self)
        pdf = self.pdf
        pdf.set_xy(x=self.x, y=self.y)

        font_size_desc = pdf.get_font_size('FONT_SIZE_DESC')
        h_font_desc = pdf.get_font_size('H_FONT_DESC')
        font_size_cont = pdf.get_font_size('FONT_SIZE_CONT', True)
        line_h_cont = DEFAULT_HEIGHT_FONT_CONTENT
        pad_bottom = 0.2

        pdf.set_font(pdf.default_font, '', font_size_desc)
        if '\n' in self.description:
            lines = [ln for ln in self.description.split('\n') if ln]
            reserva_valor = line_h_cont + pad_bottom + 0.1
            lh_desc = min(h_font_desc * 0.9, max(1.8, (self.h - reserva_valor) / max(len(lines), 1)))
            for ln in lines:
                pdf.set_x(self.x)
                pdf.cell(w=self.w, h=lh_desc, text=ln, new_x='LEFT', new_y='NEXT', align='L')
        else:
            pdf.cell(
                w=self.w,
                h=h_font_desc,
                text=self.description,
                new_x='LEFT',
                new_y='NEXT',
                align='L',
            )

        if self.type in ['protocolo', 'chave_acesso']:
            pdf.set_font(pdf.default_font, 'B', font_size_cont)
            align = 'C'
        else:
            pdf.set_font(pdf.default_font, '', font_size_cont)
            align = 'R' if self.type == 'number' else 'L'

        y_val = self.y + self.h - line_h_cont - pad_bottom
        pdf.set_xy(self.x, y_val)
        texto = self.content or ''
        if self.type == 'number' and texto and '\n' not in texto:
            pdf.cell(w=self.w, h=line_h_cont, text=texto, align=align, new_x='LEFT', new_y='TOP')
            self._content_lines = [texto]
        else:
            self._content_lines = pdf.multi_cell(
                w=self.w,
                h=line_h_cont,
                text=texto,
                align=align,
                output=MethodReturnValue.LINES,
            )
        desc_used = h_font_desc if '\n' not in self.description else (self.h - line_h_cont - pad_bottom)
        content_height = max(0.0, self.h - desc_used)
        self._max_content_lines = int(content_height // line_h_cont) if line_h_cont else 0


class NexusDanfeBlock(DanfeBlock):
    def add_fields(self, fields_list):
        for i, fields_line in enumerate(fields_list):
            fields = self.calculate_fields_width(fields_line)
            for field_info in fields:
                self.add_field(
                    NexusDanfeBasicField(
                        w=field_info.w,
                        h=self.rows_heights[i],
                        description=field_info.description,
                        content=field_info.content,
                        type=field_info.type,
                        pdf=self.pdf,
                    )
                )


def draw_taxes_nexus(self) -> None:
    """Substitui Danfe._draw_taxes — rótulo de vProd em duas linhas."""
    block_impostos = NexusDanfeBlock(
        description='CÁLCULO DO IMPOSTO',
        rows_heights=(
            DEFAULT_FIELD_HEIGHT,
            DEFAULT_FIELD_HEIGHT,
        ),
        pdf=self,
    )

    v_bc = format_number(extract_text(self.totais, 'vBC'), precision=2)
    v_icms = format_number(extract_text(self.totais, 'vICMS'), precision=2)
    v_bcst = format_number(extract_text(self.totais, 'vBCST'), precision=2)
    v_st = format_number(extract_text(self.totais, 'vST'), precision=2)
    v_pis = format_number(extract_text(self.totais, 'vPIS'), precision=2)
    v_prod = format_number(extract_text(self.totais, 'vProd'), precision=2)
    v_frete = format_number(extract_text(self.totais, 'vFrete'), precision=2)
    v_seg = format_number(extract_text(self.totais, 'vSeg'), precision=2)
    v_desc = format_number(extract_text(self.totais, 'vDesc'), precision=2)
    v_outro = format_number(extract_text(self.totais, 'vOutro'), precision=2)
    v_ipi = format_number(extract_text(self.totais, 'vIPI'), precision=2)
    v_confins = format_number(extract_text(self.totais, 'vCOFINS'), precision=2)
    v_nf = format_number(extract_text(self.totais, 'vNF'), precision=2)
    v_tot_trib = format_number(extract_text(self.totais, 'vTotTrib'), precision=2)

    fields_line1 = [
        BaseFieldInfo(w=30, description='BASE DE CÁLCULO DO ICMS', content=v_bc, type='number'),
        BaseFieldInfo(w=30, description='VALOR DO ICMS', content=v_icms, type='number'),
        BaseFieldInfo(
            w=30,
            description='BASE DE CÁLCULO DO ICMS ST',
            content=v_bcst,
            type='number',
        ),
        BaseFieldInfo(w=30, description='VALOR DO ICMS ST ', content=v_st, type='number'),
        BaseFieldInfo(
            w=30,
            description='VALOR APROX. TRIBUTOS',
            content=v_tot_trib,
            type='number',
        ),
        BaseFieldInfo(
            w=0,
            description=LABEL_VALOR_TOTAL_PRODUTOS,
            content=v_prod,
            type='number',
        ),
    ]
    fields_line2 = [
        BaseFieldInfo(w=30, description='VALOR DO FRETE', content=v_frete, type='number'),
        BaseFieldInfo(w=30, description='VALOR DO SEGURO', content=v_seg, type='number'),
        BaseFieldInfo(w=30, description='DESCONTO', content=v_desc, type='number'),
        BaseFieldInfo(
            w=30,
            description='OUTRAS DESPESAS ACESSÓRIAS',
            content=v_outro,
            type='number',
        ),
        BaseFieldInfo(w=30, description='VALOR DO IPI', content=v_ipi, type='number'),
        BaseFieldInfo(w=0, description='VALOR TOTAL DA NOTA', content=v_nf, type='number'),
    ]
    if self.display_pis_cofins:
        fields_line1.insert(
            -1,
            BaseFieldInfo(w=0, description='VALOR DO PIS', content=v_pis, type='number'),
        )
        fields_line2.insert(
            -1,
            BaseFieldInfo(w=0, description='VALOR DO COFINS', content=v_confins, type='number'),
        )
    block_impostos.add_fields([fields_line1, fields_line2])
    block_impostos.render()
