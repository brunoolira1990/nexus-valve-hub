"""
Escala adaptativa de fonte para Informações Complementares no DANFE (BFR).

Ajuste somente visual no PDF — não altera XML, infCpl nem transmissão SEFAZ.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fpdf.enums import MethodReturnValue

if TYPE_CHECKING:
    from brazilfiscalreport.danfe.danfe import Danfe

# ~5,5pt sobre FONT_SIZE_CONT da BFR com FontSize.SMALL (base ≈ 7pt).
INFCPL_FONT_BASE_FACTOR = 0.78
INFCPL_LINE_HEIGHT_RATIO = 0.38

# Auto-shrink até ~3,5pt efetivo.
INFCPL_ESCALAS_DANFE: tuple[float, ...] = (
    1.0,
    0.92,
    0.85,
    0.78,
    0.72,
    0.65,
    0.58,
    0.52,
    0.46,
    0.40,
)
INFCPL_ESCALA_MINIMA = INFCPL_ESCALAS_DANFE[-1]
INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA = 23.0
INFCPL_LARGURA_RESERVADO_FISCO = 70.0


def escala_efetiva_infcpl(font_size: float, escala: float) -> float:
    """Tamanho final do infCpl no PDF (base reduzida × auto-shrink)."""
    return font_size * escala * INFCPL_FONT_BASE_FACTOR


def normalizar_infcpl_para_danfe_pdf(obs_raw: str) -> str:
    """Preserva quebras \\n do XML; colapsa apenas espaços horizontais por linha."""
    segmentos: list[str] = []
    for linha in (obs_raw or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        seg = ' '.join(linha.split())
        if seg:
            segmentos.append(seg)
    return '\n'.join(segmentos)


def largura_campo_infcpl(danfe: Danfe) -> float:
    return danfe.edw - INFCPL_LARGURA_RESERVADO_FISCO


def _ativar_escala_infcpl(danfe: Danfe, escala: float) -> None:
    danfe._nexus_infcpl_scale = escala  # type: ignore[attr-defined]
    danfe._nexus_infcpl_scale_active = True  # type: ignore[attr-defined]


def _desativar_escala_infcpl(danfe: Danfe) -> None:
    danfe._nexus_infcpl_scale_active = False  # type: ignore[attr-defined]


def _line_height_infcpl(font_size_cont: float, escala: float) -> float:
    """Altura de linha alinhada à fonte efetiva (evita estouro vertical do rodapé)."""
    return max(font_size_cont * INFCPL_LINE_HEIGHT_RATIO, 2.0 * escala)


def _metricas_bloco_infcpl(
    danfe: Danfe,
    escala: float,
    *,
    block_height: float = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA,
) -> tuple[float, float, int, float]:
    """Retorna (line_h, h_desc, max_lines, font_size_cont)."""
    h_desc = danfe.get_font_size('H_FONT_DESC')
    font_size_cont = danfe.get_font_size('FONT_SIZE_CONT', True)
    line_h = _line_height_infcpl(font_size_cont, escala)
    area_conteudo = max(block_height - h_desc - 0.4, line_h)
    max_lines = max(1, int(area_conteudo // line_h))
    return line_h, h_desc, max_lines, font_size_cont


def _quebrar_linhas_infcpl(
    danfe: Danfe,
    texto: str,
    escala: float,
    *,
    block_height: float = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA,
) -> tuple[list[str], int]:
    """Quebra o texto em linhas (dry-run) e retorna (linhas, max_lines no bloco)."""
    _ativar_escala_infcpl(danfe, escala)
    try:
        largura = largura_campo_infcpl(danfe)
        line_h, _, max_lines, font_size_cont = _metricas_bloco_infcpl(
            danfe,
            escala,
            block_height=block_height,
        )
        danfe.set_font(danfe.default_font, '', font_size_cont)
        linhas = danfe.multi_cell(
            w=largura,
            h=line_h,
            text=texto or '',
            align='L',
            dry_run=True,
            output=MethodReturnValue.LINES,
        )
        return linhas, max_lines
    finally:
        _desativar_escala_infcpl(danfe)


def medir_linhas_infcpl(
    danfe: Danfe,
    texto: str,
    escala: float,
    *,
    block_height: float = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA,
) -> tuple[int, int]:
    """Retorna (total de linhas quebradas, máximo de linhas no bloco)."""
    linhas, max_lines = _quebrar_linhas_infcpl(
        danfe,
        texto,
        escala,
        block_height=block_height,
    )
    return len(linhas), max_lines


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


def _linhas_visiveis_infcpl(
    danfe: Danfe,
    texto: str,
    escala: float,
    *,
    block_height: float = INFCPL_ALTURA_BLOCO_PRIMEIRA_PAGINA,
) -> tuple[list[str], int]:
    """Linhas que cabem no rodapé da 1ª página (keep-together)."""
    linhas, max_lines = _quebrar_linhas_infcpl(
        danfe,
        texto,
        escala,
        block_height=block_height,
    )
    return linhas[:max_lines], max_lines


def _desenhar_linhas_infcpl(
    pdf: Danfe,
    *,
    x: float,
    y: float,
    w: float,
    h_bloco: float,
    h_desc: float,
    linhas: list[str],
    line_h: float,
    font_size_cont: float,
) -> None:
    pdf.set_font(pdf.default_font, '', font_size_cont)
    y_max = y + max(h_bloco - h_desc, line_h)
    for i, linha in enumerate(linhas):
        y_line = y + i * line_h
        if y_line + line_h > y_max + 0.05:
            break
        pdf.set_xy(x, y_line)
        pdf.cell(
            w=w,
            h=line_h,
            text=linha,
            align='L',
            new_x='LEFT',
            new_y='NEXT',
        )


def draw_additional_data_primeira_pagina(
    danfe: Danfe,
    additional_data: str,
    escala: float,
) -> tuple[list[str], int]:
    """
    Desenha bloco Dados Adicionais da 1ª página com escala Nexus no infCpl.

    O texto é limitado à altura do rodapé (keep together) — sem página de continuação.
    """
    from brazilfiscalreport.danfe.danfe_basic_field import DanfeBasicField
    from brazilfiscalreport.danfe.danfe_block import DanfeBlock
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
                line_h, _, _, font_size_cont = _metricas_bloco_infcpl(
                    pdf,
                    self._nexus_escala_campo,
                    block_height=self.h,
                )
                linhas_visiveis, _ = _linhas_visiveis_infcpl(
                    pdf,
                    self.content or '',
                    self._nexus_escala_campo,
                    block_height=self.h,
                )

                pdf.set_font(pdf.default_font, '', font_size_desc)
                pdf.cell(
                    w=self.w,
                    h=h_font_desc,
                    text=self.description,
                    new_x='LEFT',
                    new_y='NEXT',
                    align='L',
                )

                y_conteudo = pdf.get_y()
                _desenhar_linhas_infcpl(
                    pdf,
                    x=self.x,
                    y=y_conteudo,
                    w=self.w,
                    h_bloco=self.h,
                    h_desc=h_font_desc,
                    linhas=linhas_visiveis,
                    line_h=line_h,
                    font_size_cont=font_size_cont,
                )

                self._content_lines = linhas_visiveis
                self._max_content_lines = len(linhas_visiveis)
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

    linhas = campo_infcpl.get_content_lines()
    return linhas, len(linhas)
