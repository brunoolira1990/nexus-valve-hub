"""Geração da chave de acesso NF-e (44 dígitos) — sem protocolo SEFAZ."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class ChaveAcessoError(ValueError):
    """Chave de acesso inválida ou incompleta."""


@dataclass(frozen=True)
class ChaveAcessoNFe:
    chave_43: str
    digito_verificador: str
    chave_44: str
    inf_nfe_id: str

    @property
    def formatada(self) -> str:
        c = self.chave_44
        return ' '.join(c[i : i + 4] for i in range(0, 44, 4))


def calcular_digito_verificador(chave_43: str) -> str:
    if len(chave_43) != 43 or not chave_43.isdigit():
        raise ChaveAcessoError('Base da chave deve ter 43 dígitos numéricos.')
    pesos = (2, 3, 4, 5, 6, 7, 8, 9)
    soma = 0
    for i, digito in enumerate(reversed(chave_43)):
        soma += int(digito) * pesos[i % len(pesos)]
    resto = soma % 11
    if resto in (0, 1):
        return '0'
    return str(11 - resto)


def montar_chave_acesso_nfe(
    *,
    cuf: str,
    aamm: str,
    cnpj_emitente: str,
    modelo: str,
    serie: str,
    nnf: str,
    tp_emis: str,
    codigo_numerico: str,
) -> ChaveAcessoNFe:
    cuf_d = ''.join(c for c in str(cuf) if c.isdigit())[:2].zfill(2)
    aamm_d = ''.join(c for c in str(aamm) if c.isdigit())[:4].zfill(4)
    cnpj_d = ''.join(c for c in str(cnpj_emitente) if c.isdigit())[:14].zfill(14)
    mod_d = ''.join(c for c in str(modelo) if c.isdigit())[:2].zfill(2)
    ser_d = ''.join(c for c in str(serie) if c.isdigit())[:3].zfill(3)
    nnf_d = ''.join(c for c in str(nnf) if c.isdigit())[:9].zfill(9)
    tpe_d = ''.join(c for c in str(tp_emis) if c.isdigit())[:1] or '1'
    cnf_d = ''.join(c for c in str(codigo_numerico) if c.isdigit())[:8].zfill(8)

    chave_43 = f'{cuf_d}{aamm_d}{cnpj_d}{mod_d}{ser_d}{nnf_d}{tpe_d}{cnf_d}'
    dv = calcular_digito_verificador(chave_43)
    chave_44 = chave_43 + dv
    return ChaveAcessoNFe(
        chave_43=chave_43,
        digito_verificador=dv,
        chave_44=chave_44,
        inf_nfe_id=f'NFe{chave_44}',
    )


def aamm_da_emissao(dh_emi: datetime | None = None) -> str:
    dt = dh_emi or datetime.now()
    return f'{dt.year % 100:02d}{dt.month:02d}'


@dataclass(frozen=True)
class SerieNumeroChaveDfe:
    """Série e número extraídos da chave de acesso NF-e/CT-e (44 dígitos)."""

    serie: str
    numero: str
    modelo: str


def extrair_serie_numero_da_chave_dfe(chave: str | None) -> SerieNumeroChaveDfe | None:
    """
    Extrai série e número da chave de acesso (layout SEFAZ, modelos 55 e 57).

  Posições: … mod(20-21) | série(22-24) | nNF(25-33) | …
    """
    digits = ''.join(c for c in str(chave or '') if c.isdigit())
    if len(digits) != 44:
        return None
    modelo = digits[20:22]
    if modelo not in ('55', '57'):
        return None
    try:
        serie = str(int(digits[22:25]))
        numero = str(int(digits[25:34]))
    except ValueError:
        return None
    return SerieNumeroChaveDfe(serie=serie, numero=numero, modelo=modelo)
