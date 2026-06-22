"""
Escala adaptativa de fonte para Informações Complementares no DANFE (BFR).

Ajuste somente visual no PDF — não altera XML, infCpl nem transmissão SEFAZ.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fpdf.enums import MethodReturnValue

if TYPE_CHECKING:
    from brazilfiscalreport.danfe.danfe import Danfe

# Fatores sobre FONT_SIZE_CONT padrão da BFR (7pt × default_font_factor).
# 0.72 ≈ 5pt — mínimo legível conservador em DANFE A4.
INFCPL_ESCALAS_DANFE: tuple[float, ...] = (1.0, 0.92, 0.85, 0.78, 0.72)
INFCPL_ESCALA_MINIMA = INFCPL_ESCALAS_DANFE[-1]
INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA = 20.0
INFCPL_LARGURA_RESERVADO_FISCO = 70.0


def largura_campo_infcpl(danfe: Danfe) -> float:
    return danfe.edw - INFCPL_LARGURA_RESERVADO_FISCO


def _ativar_escala_infcpl(danfe: Danfe, escala: float) -> None:
    danfe._nexus_infcpl_scale = escala  # type: ignore[attr-defined]
    danfe._nexus_infcpl_scale_active = True  # type: ignore[attr-defined]


def _desativar_escala_infcpl(danfe: Danfe) -> None:
    danfe._nexus_infcpl_scale_active = False  # type: ignore[attr-defined]


def medir_linhas_infcpl(
    danfe: Danfe,
    texto: str,
    escala: float,
    *,
    block_height: float = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA,
) -> tuple[int, int]:
    """Retorna (total de linhas quebradas, máximo de linhas no bloco)."""
    from brazilfiscalreport.danfe.danfe_conf import DEFAULT_HEIGHT_FONT_CONTENT

    _ativar_escala_infcpl(danfe, escala)
    try:
        largura = largura_campo_infcpl(danfe)
        line_h = DEFAULT_HEIGHT_FONT_CONTENT * escala
        h_desc = danfe.get_font_size('H_FONT_DESC')
        max_lines = max(1, int((block_height - h_desc) // line_h))
        font_size = danfe.get_font_size('FONT_SIZE_CONT', True)
        danfe.set_font(danfe.default_font, '', font_size)
        linhas = danfe.multi_cell(
            w=largura,
            h=line_h,
            text=texto or '',
            align='L',
            output=MethodReturnValue.LINES,
        )
        return len(linhas), max_lines
    finally:
        _desativar_escala_infcpl(danfe)


def resolver_escala_infcpl_danfe(
    danfe: Danfe,
    texto: str,
    *,
    block_height: float = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA,
) -> float:
    """Maior escala em que o infCpl cabe no rodapé; senão mínima legível."""
    if not (texto or '').strip():
        return 1.0
    for escala in INFCPL_ESCALAS_DANFE:
        total, maximo = medir_linhas_infcpl(danfe, texto, escala, block_height=block_height)
        if total <= maximo:
            return escala
    return INFCPL_ESCALA_MINIMA


def draw_additional_data_primeira_pagina(
    danfe: Danfe,
    additional_data: str,
    escala: float,
) -> tuple[list[str], int]:
    """
    Desenha bloco Dados Adicionais da 1ª página com escala Nexus no infCpl.
    Equivalente ao _draw_additional_data da BFR (sem continuation_height).
    """
    from brazilfiscalreport.danfe.danfe_basic_field import DanfeBasicField
    from brazilfiscalreport.danfe.danfe_block import DanfeBlock
    from brazilfiscalreport.danfe.danfe_conf import DEFAULT_HEIGHT_FONT_CONTENT, HEIGHT_FONT_BLOCK_DESC
    from brazilfiscalreport.danfe.models import BaseFieldInfo
    from brazilfiscalreport.pdf_element import Element

    block_height = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA

    class _NexusInfcplField(DanfeBasicField):
        def __init__(self, *, escala_campo: float, **kwargs) -> None:
            self._nexus_escala_campo = escala_campo
            super().__init__(**kwargs)

        def render(self) -> None:
            Element.render(self)
            pdf = self.pdf
            pdf.set_xy(x=self.x, y=self.y)

            font_size_desc = pdf.get_font_size('FONT_SIZE_DESC')
            h_font_desc = pdf.get_font_size('H_FONT_DESC')

            _ativar_escala_infcpl(pdf, self._nexus_escala_campo)
            try:
                font_size_cont = pdf.get_font_size('FONT_SIZE_CONT', True)
                pdf.set_font(pdf.default_font, '', font_size_desc)
                pdf.cell(
                    w=self.w,
                    h=h_font_desc,
                    text=self.description,
                    new_x='LEFT',
                    new_y='NEXT',
                    align='L',
                )
                pdf.set_font(pdf.default_font, '', font_size_cont)
                line_h = DEFAULT_HEIGHT_FONT_CONTENT * self._nexus_escala_campo
                self._content_lines = pdf.multi_cell(
                    w=self.w,
                    h=line_h,
                    text=self.content or '',
                    align='L',
                    output=MethodReturnValue.LINES,
                )
                content_height = self.h - h_font_desc
                self._max_content_lines = max(1, int(content_height // line_h))
            finally:
                _desativar_escala_infcpl(pdf)

    block = DanfeBlock(description='DADOS ADICIONAIS', pdf=danfe)
    block.rows_heights = (block_height,)
    fields_line = block.calculate_fields_width(
        [
            BaseFieldInfo(
                w=0,
                description='INFORMAÇÕES COMPLEMENTARES',
                content=additional_data,
                type='info_complementares',
            ),
            BaseFieldInfo(w=70, description='RESERVADO AO FISCO', content=''),
        ],
    )

    block.render_description()
    x = block.x + block.offset_x
    y = block.y + block.offset_y

    campo_infcpl = _NexusInfcplField(
        escala_campo=escala,
        w=fields_line[0].w,
        h=block_height,
        description=fields_line[0].description,
        content=fields_line[0].content,
        type=fields_line[0].type,
        pdf=danfe,
        x=x,
        y=y,
    )
    campo_infcpl.render()
    x, y = block.get_new_position(campo_infcpl)
    danfe.set_xy(x=x, y=y)

    campo_fisco = DanfeBasicField(
        w=fields_line[1].w,
        h=block_height,
        description=fields_line[1].description,
        content=fields_line[1].content,
        type=fields_line[1].type,
        pdf=danfe,
        x=x,
        y=y,
    )
    campo_fisco.render()
    x, y = block.get_new_position(campo_fisco)
    danfe.set_xy(x=x, y=y)

    return campo_infcpl.get_content_lines(), campo_infcpl.get_max_content_lines()
