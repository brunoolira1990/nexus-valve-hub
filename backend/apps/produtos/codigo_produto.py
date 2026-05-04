"""Montagem de código e descrição para produtos com regra por família."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.produtos.models import FamiliaProduto, Polegada, Produto, RoscaConexao, ScheduleEspessura


def _normalize_spaces(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip())


def _token_in_text(text: str, token: str) -> bool:
    if not text or not token:
        return False
    escaped = re.escape(token.strip())
    return bool(re.search(rf'(^|[^A-Z0-9]){escaped}([^A-Z0-9]|$)', text.upper()))


def _descricao_rosca_comercial(rosca: RoscaConexao | None) -> str:
    if not rosca:
        return ''
    codigo = (rosca.codigo or '').strip().upper()
    desc_raw = _normalize_spaces((rosca.descricao or ''))
    desc_upper = desc_raw.upper()
    if 'PADRAO DA FAMILIA' in desc_upper or 'PADRÃO DA FAMÍLIA' in desc_upper:
        # Rosca padrão nunca deve vazar metadado interno para descrição comercial.
        return 'BSP'
    cleaned = desc_raw
    for frag in (
        '/ padrão da família',
        '/ padrao da familia',
        'padrão da família',
        'padrao da familia',
        'default',
        'sem rosca',
    ):
        cleaned = re.sub(re.escape(frag), '', cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_spaces(cleaned.strip(' /-'))
    if not cleaned and not codigo:
        return 'BSP'
    return cleaned or codigo


def _descricao_schedule_comercial(schedule: ScheduleEspessura | None) -> str:
    if not schedule:
        return ''
    desc = _normalize_spaces((schedule.descricao or ''))
    cod = _normalize_spaces((schedule.codigo_schedule or ''))
    return desc or cod


def _codigo_rosca(rosca: RoscaConexao | None) -> str:
    if not rosca:
        return ''
    return (rosca.codigo or '').strip()


def _codigo_schedule(sch: ScheduleEspessura | None) -> str:
    if not sch:
        return ''
    return (sch.codigo_schedule or '').strip()


def _codigo_pol(p: Polegada | None, *, width: int = 2) -> str:
    if not p:
        return ''
    c = (getattr(p, 'codigo_oficial', '') or p.codigo or '').strip()
    if not c.isdigit():
        return c
    w = width if width in (2, 3) else 2
    if len(c) <= w:
        return c.zfill(w)
    return c


def montar_codigo_interno(
    familia: FamiliaProduto,
    *,
    rosca: RoscaConexao | None,
    schedule: ScheduleEspessura | None,
    polegada_principal: Polegada | None,
    polegada_secundaria: Polegada | None,
) -> str:
    from apps.produtos.models import FamiliaProduto

    rule = familia.tipo_regra_codigo
    if rule == FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE:
        return ''

    fig = (familia.codigo_figura or '').strip()
    rs = _codigo_rosca(rosca)
    sch = _codigo_schedule(schedule)
    id1 = _codigo_pol(polegada_principal, width=2)
    id2 = _codigo_pol(polegada_secundaria, width=2)
    sep = (familia.separador_base_medidas or '.')[:1] or '.'

    t = FamiliaProduto.TipoRegraCodigo

    if rule == t.BASE_POLEGADA:
        return f'{fig}{sep}{id1}' if id1 else ''

    if rule == t.BASE_ROSCA_POLEGADA:
        return f'{fig}{rs}{sep}{id1}' if id1 else ''

    if rule == t.BASE_DUAS_POLEGADAS:
        if not id1 or not id2:
            return ''
        return f'{fig}{sep}{id1}{id2}'

    if rule == t.BASE_ROSCA_DUAS_POLEGADAS:
        if not id1 or not id2:
            return ''
        return f'{fig}{rs}{sep}{id1}{id2}'

    if rule == t.BASE_SCHEDULE_POLEGADA:
        if not sch or not id1:
            return ''
        return f'{fig}{sch}{sep}{id1}'

    if rule == t.BASE_SCHEDULE_DUAS_POLEGADAS:
        if not sch or not id1 or not id2:
            return ''
        return f'{fig}{sch}{sep}{id1}{id2}'

    if rule == t.BASE_ROSCA_SCHEDULE_POLEGADA:
        if rosca is None or schedule is None or not sch or not id1:
            return ''
        return f'{fig}{rs}{sch}{sep}{id1}'

    if rule == t.BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS:
        if rosca is None or schedule is None or not sch or not id1 or not id2:
            return ''
        return f'{fig}{rs}{sch}{sep}{id1}{id2}'

    if rule == t.UNDERSCORE_POLEGADA:
        id_u = _codigo_pol(polegada_principal, width=3)
        if not id_u:
            return ''
        return f'{fig}_{id_u}'

    return ''


def montar_descricao_sugerida(
    familia: FamiliaProduto,
    *,
    rosca: RoscaConexao | None,
    schedule: ScheduleEspessura | None,
    polegada_principal: Polegada | None,
    polegada_secundaria: Polegada | None,
) -> str:
    partes: list[str] = []
    base = _normalize_spaces(familia.descricao_base or '')
    base_upper = base.upper()
    if base:
        partes.append(base)
    rosca_text = _descricao_rosca_comercial(rosca)
    if rosca_text and not _token_in_text(base_upper, rosca_text):
        partes.append(rosca_text)
    schedule_text = _descricao_schedule_comercial(schedule)
    if schedule_text and not _token_in_text(base_upper, schedule_text):
        partes.append(schedule_text)
    if polegada_principal and (polegada_principal.descricao or '').strip():
        partes.append(_normalize_spaces(polegada_principal.descricao))
    if polegada_secundaria and (polegada_secundaria.descricao or '').strip():
        partes.append(f'x {_normalize_spaces(polegada_secundaria.descricao)}')
    return _normalize_spaces(' '.join(partes))


def codigo_interno_valido(codigo: str) -> bool:
    if not codigo or not codigo.strip():
        return False
    if '...' in codigo or '..' in codigo:
        return False
    return True


def produto_aplicar_codigo_completo(produto: Produto) -> None:
    from apps.produtos.models import Produto

    if produto.modo_codigo == Produto.ModoCodigo.MANUAL:
        produto.codigo_completo = (produto.codigo_completo or '').strip()
        return

    if produto.modo_codigo == Produto.ModoCodigo.LEGADO or produto.familia_id is None:
        produto.codigo_completo = produto.gerar_codigo_legado()
        return

    if not produto.familia_id:
        produto.codigo_completo = produto.gerar_codigo_legado()
        return

    familia = produto.familia
    codigo = montar_codigo_interno(
        familia,
        rosca=produto.rosca_conexao,
        schedule=produto.schedule_ref,
        polegada_principal=produto.polegada_principal_ref,
        polegada_secundaria=produto.polegada_secundaria_ref,
    )
    produto.codigo_completo = codigo
