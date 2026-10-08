"""Indicadores fiscais da operação NF-e (indFinal / indPres) — ERP 4.0.13.6.13."""

from __future__ import annotations

IND_FINAL_NAO = '0'
IND_FINAL_SIM = '1'

IND_PRES_OPCOES: dict[str, str] = {
    '0': 'Não se aplica',
    '1': 'Operação presencial',
    '2': 'Operação não presencial, internet',
    '3': 'Operação não presencial, teleatendimento',
    '4': 'NFC-e entrega em domicílio',
    '5': 'Operação presencial, fora do estabelecimento',
    '9': 'Operação não presencial, outros',
}

IND_PRES_VALIDOS = frozenset(IND_PRES_OPCOES.keys())

IND_INTERMED_NAO = '0'
IND_INTERMED_SIM = '1'


def normalizar_ind_final(val: str | None) -> str:
    v = (val or IND_FINAL_SIM).strip()
    return IND_FINAL_SIM if v == IND_FINAL_SIM else IND_FINAL_NAO


def normalizar_ind_pres(val: str | None) -> str:
    v = (val or '1').strip()
    return v if v in IND_PRES_VALIDOS else '1'


def normalizar_ind_intermed(val: str | None) -> str:
    """Indicador de intermediador (SEFAZ exige desde NT RTC — default sem intermediador)."""
    v = (val or IND_INTERMED_NAO).strip()
    return IND_INTERMED_SIM if v == IND_INTERMED_SIM else IND_INTERMED_NAO


def label_ind_final(val: str | None) -> str:
    return 'Sim (consumidor final)' if normalizar_ind_final(val) == IND_FINAL_SIM else 'Não (revenda/industrialização)'


def label_ind_pres(val: str | None) -> str:
    return IND_PRES_OPCOES.get(normalizar_ind_pres(val), normalizar_ind_pres(val))


def montar_indicadores_fiscais_payload(nf) -> dict:
    return {
        'ind_final': normalizar_ind_final(getattr(nf, 'ind_final', IND_FINAL_SIM)),
        'ind_final_label': label_ind_final(getattr(nf, 'ind_final', IND_FINAL_SIM)),
        'ind_pres': normalizar_ind_pres(getattr(nf, 'ind_pres', '1')),
        'ind_pres_label': label_ind_pres(getattr(nf, 'ind_pres', '1')),
        'indicadores_fiscais_confirmados': bool(getattr(nf, 'indicadores_fiscais_confirmados', False)),
    }
