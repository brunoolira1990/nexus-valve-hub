"""Leitura normalizada de snapshot fiscal em itens de NF-e Saída (sem recalcular regras)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.regras_fiscais.reforma_tributaria_config import (
    REFORMA_SNAPSHOT_BASE_KEYS,
    REFORMA_TRIBUTARIA_KEYS,
    normalizar_percentual_reforma,
    normalizar_reforma_tributaria,
    reforma_tributaria_preenchida,
)
from apps.fiscal.nfe_saida_reforma_calculo import status_reforma_snapshot


def _text(val: Any) -> str:
    if val is None:
        return ''
    return str(val).strip()


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    s = str(val).strip()
    if ',' in s:
        return normalizar_percentual_reforma(val)
    try:
        return Decimal(s)
    except Exception:
        return normalizar_percentual_reforma(val)


def _snap_val(snap: dict | None, *keys: str, default: str = '') -> str:
    data = snap or {}
    for key in keys:
        v = data.get(key)
        if v not in (None, ''):
            return _text(v)
    return default


def cfop_from_snapshot_fiscal(snapshot: dict | None) -> str:
    snap = snapshot or {}
    for key in ('cfop', 'cfop_venda', 'cfop_saida', 'cfop_st'):
        cfop = _only_digits_cfop(snap.get(key))
        if cfop:
            return cfop
    return ''


def _only_digits_cfop(val: Any) -> str:
    digits = ''.join(c for c in _text(val) if c.isdigit())
    return digits[:4] if digits else ''


def normalize_snapshot_fiscal_for_nfe(snapshot: dict | None) -> dict:
    snap = dict(snapshot or {})
    cfop = cfop_from_snapshot_fiscal(snap)
    if cfop:
        snap['cfop'] = cfop
    return snap


def get_ncm_snapshot(snapshot: dict | None) -> str:
    snap = snapshot or {}
    ncm = _snap_val(snap, 'ncm')
    if ncm:
        return ''.join(c for c in ncm if c.isdigit())[:8]
    return ''


REFORMA_SNAPSHOT_CALCULO_KEYS = (
    'base_cbs',
    'base_ibs',
    'base_ibs_estadual',
    'base_ibs_municipal',
    'valor_cbs',
    'valor_ibs_estadual',
    'valor_ibs_municipal',
    'valor_ibs_uf',
    'valor_ibs_mun',
    'valor_total_ibs_cbs',
    *REFORMA_SNAPSHOT_BASE_KEYS,
    'diagnosticos_base_reforma',
)


def get_reforma_tributaria_snapshot(snapshot: dict | None) -> dict[str, Any] | None:
    snap = snapshot or {}
    raw = snap.get('reforma_tributaria') or snap.get('ibs_cbs')
    if not isinstance(raw, dict):
        return None
    norm = dict(normalizar_reforma_tributaria(raw) or {})
    for key in REFORMA_SNAPSHOT_CALCULO_KEYS:
        if key in raw and raw[key] not in (None, ''):
            norm[key] = raw[key]
    return norm or None


def reforma_configurada_no_snapshot(snapshot: dict | None) -> bool:
    return reforma_tributaria_preenchida(get_reforma_tributaria_snapshot(snapshot))


def get_icms_snapshot(snapshot: dict | None) -> dict[str, str]:
    snap = snapshot or {}
    return {
        'cst_icms': _snap_val(snap, 'cst_icms', 'icms_cst', 'CST'),
        'csosn': _snap_val(snap, 'csosn', 'CSOSN'),
        'modalidade_bc': _snap_val(snap, 'modalidade_bc_icms', 'mod_bc_icms'),
        'base': _snap_val(snap, 'base_icms', 'v_bc_icms'),
        'aliquota': _snap_val(
            snap,
            'aliquota_icms',
            'icms_saida_percentual',
            'p_icms',
        ),
        'valor': _snap_val(snap, 'valor_icms', 'v_icms'),
        'reducao_bc': _snap_val(snap, 'reducao_bc_icms', 'p_red_bc'),
        'codigo_beneficio': _snap_val(snap, 'codigo_beneficio_icms', 'c_benef'),
        'motivo_desoneracao': _snap_val(snap, 'motivo_desoneracao_icms', 'mot_des_icms'),
        'valor_icms_deson': _snap_val(snap, 'valor_icms_deson', 'v_icms_deson'),
        'icms_st': _snap_val(snap, 'icms_st_aplicavel', 'icms_st'),
        'cst_icms_st': _snap_val(snap, 'cst_icms_st'),
        'base_icms_st': _snap_val(snap, 'base_icms_st', 'v_bc_st'),
        'aliquota_icms_st': _snap_val(snap, 'aliquota_icms_st', 'p_icms_st'),
        'valor_icms_st': _snap_val(snap, 'valor_icms_st', 'v_icms_st'),
        'fcp': _snap_val(snap, 'fcp', 'valor_fcp', 'v_fcp'),
    }


def get_ipi_snapshot(snapshot: dict | None) -> dict[str, str]:
    snap = snapshot or {}
    return {
        'cst': _snap_val(snap, 'cst_ipi', 'ipi_cst'),
        'base': _snap_val(snap, 'base_ipi', 'v_bc_ipi'),
        'aliquota': _snap_val(snap, 'aliquota_ipi', 'ipi_saida_percentual', 'p_ipi'),
        'valor': _snap_val(snap, 'valor_ipi', 'v_ipi'),
    }


def get_pis_snapshot(snapshot: dict | None) -> dict[str, str]:
    snap = snapshot or {}
    return {
        'cst': _snap_val(snap, 'cst_pis', 'pis_cst'),
        'base': _snap_val(snap, 'base_pis', 'v_bc_pis'),
        'aliquota': _snap_val(snap, 'aliquota_pis', 'pis_saida_percentual', 'p_pis'),
        'valor': _snap_val(snap, 'valor_pis', 'v_pis'),
        'deduzir_icms_base': _snap_val(snap, 'deduzir_icms_base_pis', 'pis_cofins_base_deduz_icms'),
    }


def get_cofins_snapshot(snapshot: dict | None) -> dict[str, str]:
    snap = snapshot or {}
    return {
        'cst': _snap_val(snap, 'cst_cofins', 'cofins_cst'),
        'base': _snap_val(snap, 'base_cofins', 'v_bc_cofins'),
        'aliquota': _snap_val(snap, 'aliquota_cofins', 'cofins_saida_percentual', 'p_cofins'),
        'valor': _snap_val(snap, 'valor_cofins', 'v_cofins'),
        'deduzir_icms_base': _snap_val(snap, 'deduzir_icms_base_cofins', 'pis_cofins_base_deduz_icms'),
    }


def montar_reforma_item_exibicao(reforma: dict[str, Any] | None, *, valor_produto: Decimal) -> dict[str, Any]:
    """Valores estimados para conferência (alíquotas × base comercial quando não há valor no snapshot)."""
    norm = reforma or {}
    base = _dec(norm.get('base_cbs') or norm.get('base_ibs') or valor_produto)
    ali_cbs = _dec(norm.get('aliquota_cbs'))
    ali_ibs_uf = _dec(norm.get('aliquota_ibs_estadual'))
    ali_ibs_mun = _dec(norm.get('aliquota_ibs_municipal'))
    v_cbs = _dec(norm.get('valor_cbs'))
    v_ibs_uf = _dec(norm.get('valor_ibs_estadual') or norm.get('valor_ibs_uf'))
    v_ibs_mun = _dec(norm.get('valor_ibs_municipal') or norm.get('valor_ibs_mun'))
    if v_cbs == 0 and ali_cbs and base:
        v_cbs = (base * ali_cbs / Decimal('100')).quantize(Decimal('0.01'))
    if v_ibs_uf == 0 and ali_ibs_uf and base:
        v_ibs_uf = (base * ali_ibs_uf / Decimal('100')).quantize(Decimal('0.01'))
    if v_ibs_mun == 0 and ali_ibs_mun and base:
        v_ibs_mun = (base * ali_ibs_mun / Decimal('100')).quantize(Decimal('0.01'))
    return {
        'cst_ibs_cbs': _text(norm.get('cst_ibs_cbs')),
        'classificacao_tributaria': _text(norm.get('classificacao_tributaria')),
        'base_cbs': str(norm.get('base_cbs') or base),
        'aliquota_cbs': str(ali_cbs),
        'valor_cbs': str(v_cbs),
        'reducao_cbs': _text(norm.get('reducao_cbs')),
        'diferimento_cbs': _text(norm.get('diferimento_cbs')),
        'credito_presumido_cbs': _text(norm.get('credito_presumido_cbs')),
        'base_ibs': str(norm.get('base_ibs') or base),
        'base_ibs_estadual': str(norm.get('base_ibs_estadual') or norm.get('base_ibs') or base),
        'aliquota_ibs_estadual': str(ali_ibs_uf),
        'valor_ibs_estadual': str(v_ibs_uf),
        'base_ibs_municipal': str(norm.get('base_ibs_municipal') or base),
        'aliquota_ibs_municipal': str(ali_ibs_mun),
        'valor_ibs_municipal': str(v_ibs_mun),
        'reducao_ibs': _text(norm.get('reducao_ibs')),
        'diferimento_ibs': _text(norm.get('diferimento_ibs')),
        'credito_presumido_ibs': _text(norm.get('credito_presumido_ibs')),
        'observacoes': _text(norm.get('observacoes')),
        'total_ibs_cbs': str(v_cbs + v_ibs_uf + v_ibs_mun),
        'base_original_reforma': _text(norm.get('base_original_reforma')),
        'base_ibs_cbs': _text(norm.get('base_ibs_cbs') or norm.get('base_cbs') or base),
        'modo_base_ibs_cbs': _text(norm.get('modo_base_ibs_cbs')) or 'BASE_CHEIA_OPERACAO',
        'valor_deduzido_icms': _text(norm.get('valor_deduzido_icms')),
        'valor_deduzido_pis': _text(norm.get('valor_deduzido_pis')),
        'valor_deduzido_cofins': _text(norm.get('valor_deduzido_cofins')),
        'valor_deduzido_ipi': _text(norm.get('valor_deduzido_ipi')),
        'valor_deduzido_iss': _text(norm.get('valor_deduzido_iss')),
        'formula_base_ibs_cbs': _text(norm.get('formula_base_ibs_cbs')) or 'vProd',
        'fonte_regra_base_ibs_cbs': _text(norm.get('fonte_regra_base_ibs_cbs')) or 'pendente',
        'status_base_reforma': _text(norm.get('status_base_reforma')) or 'pendente_confirmacao',
        'chaves_preenchidas': [k for k in REFORMA_TRIBUTARIA_KEYS if _text(norm.get(k))],
    }


def status_reforma_item(reforma: dict[str, Any] | None) -> str:
    st = status_reforma_snapshot(reforma)
    if st == 'CALCULADA':
        return 'OK'
    return st
