"""cBenef SP — literal SEM CBENEF e validação para CST com benefício fiscal."""

from __future__ import annotations

import re
from decimal import Decimal

CBENEF_SEM_CODIGO_LITERAL = 'SEM CBENEF'

MSG_CBENEF_SP_CST20_REDUCAO = (
    'SEFAZ-SP pode rejeitar CST 20 com redução sem cBenef. '
    'Informe o código específico ou selecione SEM CBENEF quando não houver código aplicável.'
)

_CBENEF_SEM_XML_RE = re.compile(
    r'<(?:[\w]+:)?cBenef>\s*SEM\s+CBENEF\s*</(?:[\w]+:)?cBenef>',
    re.IGNORECASE,
)


def normalizar_codigo_beneficio_icms(val: str | None) -> str:
    """Normaliza código de benefício; SEM CBENEF sempre em maiúsculas."""
    raw = (val or '').strip()
    if not raw:
        return ''
    compact = ' '.join(raw.upper().split())
    if compact == 'SEM CBENEF':
        return CBENEF_SEM_CODIGO_LITERAL
    return raw[:16]


def codigo_beneficio_icms_preenchido(val: str | None) -> bool:
    return bool(normalizar_codigo_beneficio_icms(val))


def ocultar_sem_cbenef_para_danfe(xml: str) -> str:
    """
    Remove apenas ``<cBenef>SEM CBENEF</cBenef>`` de cópia do XML para render DANFE.

    O XML fiscal armazenado/transmitido não deve passar por esta função.
    Códigos específicos de benefício permanecem visíveis no DANFE.
    """
    if not (xml or '').strip():
        return xml
    return _CBENEF_SEM_XML_RE.sub('', xml)


def _cst_icms_snapshot(snapshot: dict) -> str:
    cst = str(snapshot.get('cst_icms') or snapshot.get('icms_cst') or snapshot.get('CST') or '').strip()
    return cst.zfill(2)[:2] if cst else ''


def _reducao_bc_pct_snapshot(snapshot: dict) -> Decimal:
    raw = snapshot.get('reducao_bc_icms') or snapshot.get('p_red_bc') or ''
    if raw in (None, ''):
        return Decimal('0')
    try:
        return Decimal(str(raw).replace(',', '.'))
    except Exception:
        return Decimal('0')


def item_exige_cbenef_sp_cst20_reducao(snapshot: dict | None, *, uf_emitente: str) -> bool:
    """SP + CST 20 + redução de BC — cenário da rejeição 930."""
    if (uf_emitente or '').strip().upper() != 'SP':
        return False
    snap = snapshot or {}
    if _cst_icms_snapshot(snap) != '20':
        return False
    return _reducao_bc_pct_snapshot(snap) > 0


def pendencia_cbenef_sp_item(
    snapshot: dict | None,
    *,
    uf_emitente: str,
    rotulo_item: str = 'Item',
) -> str | None:
    if not item_exige_cbenef_sp_cst20_reducao(snapshot, uf_emitente=uf_emitente):
        return None
    snap = snapshot or {}
    if codigo_beneficio_icms_preenchido(snap.get('codigo_beneficio_icms')):
        return None
    return f'{rotulo_item}: {MSG_CBENEF_SP_CST20_REDUCAO}'
