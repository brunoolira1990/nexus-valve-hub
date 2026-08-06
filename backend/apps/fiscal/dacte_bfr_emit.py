"""Ajustes de layout DACTE (BrazilFiscalReport) — box do emitente."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def patch_draw_header_emitente(dacte, draw_header_original: Callable[..., Any]) -> None:
    """
    O BFR 0.7.4 posiciona o endereço em Y fixo (y_text+6). Quando o xNome quebra
    linha, o CNPJ é desenhado em cima do restante do nome → ``LTDACNPJ``.

    Interceptamos o ``set_xy`` pós-nome e o texto do endereço para:
    - colocar o bloco do endereço abaixo do nome;
    - separar CNPJ e IE em linhas distintas (caixa estreita).
    """
    orig_set_xy = dacte.set_xy
    orig_multi_cell = dacte.multi_cell
    state = {'name_drawn': False, 'fix_next_xy': False}

    def set_xy(x=0, y=0):  # noqa: ANN001
        if state['fix_next_xy']:
            state['fix_next_xy'] = False
            return orig_set_xy(x=x, y=dacte.get_y() + 0.5)
        return orig_set_xy(x=x, y=y)

    def multi_cell(w, h=None, text='', border=0, align='J', **kwargs):  # noqa: ANN001
        if 'text' in kwargs:
            text = kwargs.pop('text')

        if not state['name_drawn'] and text and text == getattr(dacte, 'emit_name', None):
            state['name_drawn'] = True
            state['fix_next_xy'] = True
            return orig_multi_cell(w, h, text=text, border=border, align=align, **kwargs)

        if state['name_drawn'] and isinstance(text, str) and text.startswith('CNPJ:'):
            lines = text.split('\n')
            if lines and ' IE: ' in lines[0]:
                cnpj_part, ie_part = lines[0].split(' IE: ', 1)
                text = '\n'.join([cnpj_part, f'IE: {ie_part}', *lines[1:]])
            return orig_multi_cell(w, h, text=text, border=border, align=align, **kwargs)

        return orig_multi_cell(w, h, text=text, border=border, align=align, **kwargs)

    dacte.set_xy = set_xy  # type: ignore[method-assign]
    dacte.multi_cell = multi_cell  # type: ignore[method-assign]
    try:
        draw_header_original(dacte)
    finally:
        dacte.set_xy = orig_set_xy  # type: ignore[method-assign]
        dacte.multi_cell = orig_multi_cell  # type: ignore[method-assign]
