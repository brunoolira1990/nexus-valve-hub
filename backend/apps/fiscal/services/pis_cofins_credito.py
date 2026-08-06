"""Classificação de CST PIS/COFINS para crédito/débito na apuração gerencial.

Regras (EFD Contribuições — simplificado):
- Crédito na entrada: CST 50–56 e 60–67 (quando regime permite crédito).
- Débito na saída: CST 01–05 (contribuição típica).
- Regime: apenas Lucro Real libera crédito; Lucro Presumido / Simples / vazio → sem crédito.

CST 01–05 NÃO geram crédito de entrada (são situações de débito/contribuição).
"""

from __future__ import annotations

import re
from typing import Literal

RegimeApuracaoPisCofins = Literal['LUCRO_REAL', 'LUCRO_PRESUMIDO', 'SIMPLES', 'OUTRO', 'INDEFINIDO']

# Crédito de PIS/COFINS (entrada) — tabela típica EFD Contribuições
CST_PIS_COFINS_CREDITO: frozenset[str] = frozenset(
    {f'{i:02d}' for i in range(50, 57)} | {f'{i:02d}' for i in range(60, 68)}
)

# Débito / contribuição (saída)
CST_PIS_COFINS_DEBITO: frozenset[str] = frozenset({'01', '02', '03', '04', '05'})


def normalizar_cst_pis_cofins(cst: str | None) -> str:
    dig = re.sub(r'\D', '', str(cst or ''))
    if not dig:
        return ''
    return dig.zfill(2)[-2:]


def classificar_regime_tributario(regime_raw: str | None) -> RegimeApuracaoPisCofins:
    t = (regime_raw or '').strip().upper()
    if not t:
        return 'INDEFINIDO'
    t_compact = re.sub(r'[^A-Z0-9]', '', t)
    if 'SIMPLES' in t_compact or t_compact in {'1', '01'}:
        return 'SIMPLES'
    if 'PRESUMIDO' in t_compact or 'LP' == t_compact:
        return 'LUCRO_PRESUMIDO'
    if 'REAL' in t_compact and 'PRESUMIDO' not in t_compact:
        return 'LUCRO_REAL'
    if t_compact in {'3', '03'}:  # CRT/código comum Lucro Real em alguns cadastros
        return 'LUCRO_REAL'
    if t_compact in {'2', '02'}:
        return 'LUCRO_PRESUMIDO'
    return 'OUTRO'


def regime_permite_credito_pis_cofins(regime: RegimeApuracaoPisCofins | str | None) -> bool:
    """Somente Lucro Real apropria crédito de PIS/COFINS não-cumulativo nesta V1."""
    if isinstance(regime, str) and regime not in (
        'LUCRO_REAL',
        'LUCRO_PRESUMIDO',
        'SIMPLES',
        'OUTRO',
        'INDEFINIDO',
    ):
        regime = classificar_regime_tributario(regime)
    return regime == 'LUCRO_REAL'


def cst_pis_cofins_gera_credito(
    cst: str | None,
    *,
    regime_tributario: str | None = None,
    regime_classificado: RegimeApuracaoPisCofins | None = None,
) -> bool:
    """
    True se o item de entrada pode contar como crédito gerencial de PIS/COFINS.

    Exige: CST de crédito E regime Lucro Real.
    """
    cst_n = normalizar_cst_pis_cofins(cst)
    if cst_n not in CST_PIS_COFINS_CREDITO:
        return False
    reg = regime_classificado or classificar_regime_tributario(regime_tributario)
    return regime_permite_credito_pis_cofins(reg)


def cst_pis_cofins_gera_debito(cst: str | None) -> bool:
    """True se CST tipicamente gera débito/contribuição na saída."""
    return normalizar_cst_pis_cofins(cst) in CST_PIS_COFINS_DEBITO
