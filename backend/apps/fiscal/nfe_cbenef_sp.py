"""cBenef SP — códigos fiscais reais vs. marcadores de UI (nunca serializar no XML).

Histórico: o marcador ``SEM CBENEF`` era persistido e emitido em ``<cBenef>``, o que
gera rejeição SEFAZ cStat 946. Marcadores de interface / textos descritivos devem
omitir a tag; operação com CST 20 + redução em SP exige código efetivo (ex. SP020120).
"""

from __future__ import annotations

import re
from decimal import Decimal

# Marcador legado de UI — NÃO é código fiscal e NÃO deve ir no XML.
CBENEF_SEM_CODIGO_LITERAL = 'SEM CBENEF'

MSG_CBENEF_SP_CST20_REDUCAO = (
    'SEFAZ-SP rejeita CST 20 com redução sem cBenef válido (cStat 946). '
    'Informe o código de benefício efetivo da operação (ex.: SP020120 / Artigo 12). '
    'Marcadores como «SEM CBENEF» não são códigos fiscais.'
)

MSG_CBENEF_MARCADOR_INVALIDO = (
    'Código de benefício ICMS contém texto descritivo (ex.: SEM CBENEF / SEM BENEFÍCIO), '
    'não um cBenef fiscal. Remova o marcador: deixe em branco para omitir a tag '
    'ou informe o código oficial (ex.: SP020120).'
)

_CBENEF_SEM_XML_RE = re.compile(
    r'<(?:[\w]+:)?cBenef>\s*SEM\s+CBENEF\s*</(?:[\w]+:)?cBenef>',
    re.IGNORECASE,
)

# Marcadores de UI / textos descritivos — sem espaços após compactação.
_MARCADORES_CBENEF_COMPACTOS = frozenset(
    {
        'SEM CBENEF',
        'SEM BENEFICIO',
        'SEM BENEFÍCIO',
        'SEM CODIGO',
        'SEM CÓDIGO',
        'SEM CODIGO ESPECIFICO',
        'SEM CÓDIGO ESPECÍFICO',
        'N/A',
        'NA',
        '-',
        '—',
        'NAO INFORMADO',
        'NÃO INFORMADO',
    }
)

_MARCADORES_CBENEF_SEM_ESPACO = frozenset(
    {
        'SEMCBENEF',
        'SEMBENEFICIO',
        'SEMCODIGO',
        'SEMCODIGOESPECIFICO',
    }
)


def _compact_spaces_upper(val: str) -> str:
    return ' '.join((val or '').strip().upper().split())


def eh_marcador_cbenef_nao_fiscal(val: str | None) -> bool:
    """True para labels/marcadores de UI que nunca devem virar ``<cBenef>``."""
    raw = (val or '').strip()
    if not raw:
        return False
    compact = _compact_spaces_upper(raw)
    if compact in _MARCADORES_CBENEF_COMPACTOS:
        return True
    nospace = compact.replace(' ', '').replace('Í', 'I').replace('Ó', 'O')
    if nospace in _MARCADORES_CBENEF_SEM_ESPACO:
        return True
    # Qualquer valor com espaço restantes costuma ser label, não cBenef.
    if ' ' in compact:
        return True
    return False


def normalizar_codigo_beneficio_icms(val: str | None) -> str:
    """Normaliza para persistência/leitura; marcadores legados ficam canônicos."""
    raw = (val or '').strip()
    if not raw:
        return ''
    if eh_marcador_cbenef_nao_fiscal(raw):
        compact = _compact_spaces_upper(raw)
        # Mantém o literal histórico mais comum para UI legado; XML ignora.
        if compact.replace(' ', '') in {'SEMCBENEF'} or compact == 'SEM CBENEF':
            return CBENEF_SEM_CODIGO_LITERAL
        return compact
    return raw[:16]


def codigo_beneficio_icms_para_xml(val: str | None) -> str | None:
    """Código a emitir em ``<cBenef>``, ou ``None`` para omitir a tag."""
    norm = normalizar_codigo_beneficio_icms(val)
    if not norm or eh_marcador_cbenef_nao_fiscal(norm):
        return None
    return norm[:16]


def codigo_beneficio_icms_para_snapshot(val: str | None) -> str:
    """Valor a gravar no snapshot fiscal (marcadores viram vazio)."""
    return codigo_beneficio_icms_para_xml(val) or ''


def codigo_beneficio_icms_preenchido(val: str | None) -> bool:
    """True somente se há código fiscal serializável (não marcador / vazio)."""
    return codigo_beneficio_icms_para_xml(val) is not None


def ocultar_sem_cbenef_para_danfe(xml: str) -> str:
    """
    Remove ``<cBenef>SEM CBENEF</cBenef>`` de cópia do XML para render DANFE
    (XMLs históricos). O path de emissão não deve mais gerar esse literal.
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
    """SP + CST 20 + redução de BC — cenário das rejeições 930/946."""
    if (uf_emitente or '').strip().upper() != 'SP':
        return False
    snap = snapshot or {}
    if _cst_icms_snapshot(snap) != '20':
        return False
    return _reducao_bc_pct_snapshot(snap) > 0


def pendencia_cbenef_marcador_item(
    snapshot: dict | None,
    *,
    rotulo_item: str = 'Item',
) -> str | None:
    """Bloqueia emissão se o snapshot ainda carrega marcador descritivo."""
    snap = snapshot or {}
    bruto = snap.get('codigo_beneficio_icms') or snap.get('c_benef') or ''
    if not str(bruto).strip():
        return None
    if eh_marcador_cbenef_nao_fiscal(bruto):
        return f'{rotulo_item}: {MSG_CBENEF_MARCADOR_INVALIDO}'
    return None


def pendencia_cbenef_sp_item(
    snapshot: dict | None,
    *,
    uf_emitente: str,
    rotulo_item: str = 'Item',
) -> str | None:
    """Pendência CST 20+redução SP sem código fiscal efetivo (não cobre marcadores)."""
    snap = snapshot or {}
    if not item_exige_cbenef_sp_cst20_reducao(snap, uf_emitente=uf_emitente):
        return None
    if codigo_beneficio_icms_preenchido(snap.get('codigo_beneficio_icms')):
        return None
    return f'{rotulo_item}: {MSG_CBENEF_SP_CST20_REDUCAO}'
