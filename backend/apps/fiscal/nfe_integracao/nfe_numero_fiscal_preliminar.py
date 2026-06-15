"""Política de numeração fiscal preliminar — usa configuração por empresa/ambiente (sem consumir sequência)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import (
    MSG_AMBIENTE_NAO_DEFINIDO,
    ambiente_emissao_nfe_definido,
)
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao


class NumeroFiscalPreliminarError(ValueError):
    """Numeração fiscal preliminar indisponível."""


@dataclass(frozen=True)
class NumeroFiscalPreliminar:
    serie: str
    nnf: str
    codigo_numerico: str
    numero_interno_ref: str
    politica: str


def _serie_digits(serie: str) -> str:
    digits = ''.join(c for c in str(serie) if c.isdigit())
    return (digits or '900')[:3].zfill(3)


def _nnf_apenas_digitos(numero: str | None) -> str:
    digits = ''.join(c for c in str(numero or '') if c.isdigit())
    return digits[:9] if digits else ''


def numero_interno_e_fiscal_oficial(numero: str | None) -> bool:
    """True quando o número interno já é só dígitos (possível nNF fiscal futuro)."""
    n = (numero or '').strip()
    return bool(n) and n.isdigit() and len(n) <= 9


def resolver_numero_fiscal_preliminar(nfe_saida: NFeSaida) -> NumeroFiscalPreliminar:
    """
    Exibe série/nNF da configuração do ambiente da NF-e (próximo número) ou numeração reservada.
    Não incrementa proximo_numero — apenas leitura para XML/DANFE preliminar.
    """
    numero_ref = (nfe_saida.numero or '').strip()

    if nfe_saida.numero_nfe and nfe_saida.serie_nfe:
        return NumeroFiscalPreliminar(
            serie=_serie_digits(nfe_saida.serie_nfe),
            nnf=_nnf_apenas_digitos(nfe_saida.numero_nfe).zfill(9),
            codigo_numerico=(nfe_saida.codigo_numerico or f'{int(nfe_saida.pk) % 100000000:08d}'),
            numero_interno_ref=numero_ref or str(nfe_saida.pk),
            politica='numeracao_reservada_emissao',
        )

    if not ambiente_emissao_nfe_definido(nfe_saida):
        raise NumeroFiscalPreliminarError(MSG_AMBIENTE_NAO_DEFINIDO)

    ambiente = (nfe_saida.ambiente_emissao or '').strip()

    try:
        empresa = resolver_empresa_emitente_nfe(nfe_saida)
        cfg = obter_config_numeracao(empresa.pk, ambiente=ambiente)
        nnf = str(int(cfg.proximo_numero))[:9].zfill(9)
        return NumeroFiscalPreliminar(
            serie=_serie_digits(cfg.serie),
            nnf=nnf,
            codigo_numerico=f'{int(nfe_saida.pk) % 100000000:08d}',
            numero_interno_ref=numero_ref or str(nfe_saida.pk),
            politica=f'config_{ambiente}_proximo_numero',
        )
    except NFeNumeracaoError as exc:
        raise NumeroFiscalPreliminarError(str(exc)) from exc
