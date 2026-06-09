"""Chaves e helpers para reforma_tributaria (JSON) em RegraFiscalEntrada."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

REFORMA_PERCENT_KEYS = frozenset(
    {
        'aliquota_cbs',
        'aliquota_ibs_estadual',
        'aliquota_ibs_municipal',
        'reducao_cbs',
        'reducao_ibs',
        'diferimento_cbs',
        'diferimento_ibs',
        'credito_presumido_cbs',
        'credito_presumido_ibs',
    },
)

REFORMA_TRIBUTARIA_KEYS = (
    'cst_ibs_cbs',
    'classificacao_tributaria',
    'aliquota_cbs',
    'aliquota_ibs_estadual',
    'aliquota_ibs_municipal',
    'reducao_cbs',
    'reducao_ibs',
    'diferimento_cbs',
    'diferimento_ibs',
    'credito_presumido_cbs',
    'credito_presumido_ibs',
    'modo_base_ibs_cbs',
    'deduzir_icms_base_ibs_cbs',
    'deduzir_pis_base_ibs_cbs',
    'deduzir_cofins_base_ibs_cbs',
    'deduzir_ipi_base_ibs_cbs',
    'deduzir_iss_base_ibs_cbs',
    'fonte_regra_base_ibs_cbs',
    'observacoes',
)

REFORMA_SNAPSHOT_BASE_KEYS = (
    'base_original_reforma',
    'base_ibs_cbs',
    'modo_base_ibs_cbs',
    'valor_deduzido_icms',
    'valor_deduzido_pis',
    'valor_deduzido_cofins',
    'valor_deduzido_ipi',
    'valor_deduzido_iss',
    'formula_base_ibs_cbs',
    'fonte_regra_base_ibs_cbs',
    'status_base_reforma',
)


def normalizar_percentual_reforma(valor: Any) -> Decimal:
    """Converte percentual pt-BR/en para Decimal (ex.: "0,1" -> 0.1)."""
    if valor is None or valor == '':
        return Decimal('0')
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    s = str(valor).strip().replace('%', '')
    if not s:
        return Decimal('0')
    if ',' in s:
        if '.' in s:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '.')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def percentual_reforma_para_snapshot(valor: Any) -> str:
    d = normalizar_percentual_reforma(valor)
    if d == 0:
        return '0'
    q = str(d.quantize(Decimal('0.0001'))).rstrip('0').rstrip('.')
    return q or '0'


def _valor_preenchido(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (int, float, bool)):
        return True
    if isinstance(val, dict):
        return any(_valor_preenchido(v) for v in val.values())
    if isinstance(val, list):
        return any(_valor_preenchido(v) for v in val)
    return bool(val)


def normalizar_reforma_tributaria(data: Any) -> dict[str, Any] | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, Any] = {}
    for key in REFORMA_TRIBUTARIA_KEYS:
        if key not in data:
            continue
        raw = data[key]
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped:
                if key in REFORMA_PERCENT_KEYS:
                    out[key] = percentual_reforma_para_snapshot(stripped)
                else:
                    out[key] = stripped
        elif _valor_preenchido(raw):
            if key in REFORMA_PERCENT_KEYS:
                out[key] = percentual_reforma_para_snapshot(raw)
            else:
                out[key] = raw
    return out or None


def reforma_tributaria_preenchida(data: Any) -> bool:
    return bool(normalizar_reforma_tributaria(data))


def reforma_tributaria_para_snapshot(data: Any) -> dict[str, str]:
    norm = normalizar_reforma_tributaria(data)
    if not norm:
        return {}
    return {key: str(val) if not isinstance(val, str) else val for key, val in norm.items()}


def resumo_reforma_tributaria(data: Any) -> str:
    """Resumo curto para matriz/tooltip (CST e classificação)."""
    norm = normalizar_reforma_tributaria(data)
    if not norm:
        return ''
    partes: list[str] = []
    cst = str(norm.get('cst_ibs_cbs') or '').strip()
    if cst:
        partes.append(f'CST {cst}')
    classificacao = str(norm.get('classificacao_tributaria') or '').strip()
    if classificacao:
        partes.append(f'Class. {classificacao}')
    return ' · '.join(partes)
