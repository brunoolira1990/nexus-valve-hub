"""Endereço fiscal no XML NF-e — município IBGE do destinatário (sem reutilizar cMunFG)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.nfe_emissao.xml_serializacao import codigo_municipio_ibge
from apps.fiscal.nfe_saida_preview import _text


def _digits(val: str | None, *, max_len: int | None = None) -> str:
    d = ''.join(c for c in str(val or '') if c.isdigit())
    if max_len:
        return d[:max_len]
    return d

MSG_CMUN_DEST_INCOMPATIVEL = (
    'Endereço fiscal do destinatário inconsistente: cidade {cidade}/{uf} possui cMun incompatível. '
    'Corrija o cadastro antes de gerar XML.'
)


def resolver_c_mun_destinatario(dest: dict[str, Any]) -> str:
    """
    Código IBGE do município do destinatário.
    Nunca usa cMunFG do emitente nem default de São Paulo.
    """
    uf = _text(dest.get('uf'))
    cidade = _text(dest.get('cidade'))
    c_mun = _digits(dest.get('c_mun'), max_len=7)
    if c_mun and c_mun != '3500000':
        return c_mun
    return codigo_municipio_ibge(uf, cidade=cidade)


def c_mun_compativel_com_cidade_uf(c_mun: str, *, uf: str, cidade: str) -> bool:
    """Verifica coerência entre cMun informado e UF/cidade (via tabela interna de fallback)."""
    if len(c_mun) != 7:
        return False
    esperado = codigo_municipio_ibge(uf, cidade=cidade)
    if c_mun == esperado:
        return True
    # cMun explícito no cadastro pode divergir do fallback por capital — bloquear só incoerências óbvias
    uf_u = _text(uf).upper()[:2]
    if uf_u == 'PA' and c_mun == '3550308':
        return False
    if uf_u == 'SP' and c_mun == '1501402':
        return False
    return c_mun[:2] == esperado[:2] if len(esperado) == 7 else True


def validar_c_mun_destinatario(dados: dict[str, Any]) -> list[str]:
    dest = dados.get('destinatario') or {}
    uf = _text(dest.get('uf'))
    cidade = _text(dest.get('cidade'))
    if not uf or not cidade:
        return []
    c_informado = _digits(dest.get('c_mun'), max_len=7)
    c_resolvido = resolver_c_mun_destinatario(dest)
    if c_informado and c_informado != '3500000' and not c_mun_compativel_com_cidade_uf(
        c_informado,
        uf=uf,
        cidade=cidade,
    ):
        return [MSG_CMUN_DEST_INCOMPATIVEL.format(cidade=cidade.upper(), uf=uf.upper())]
    return []


def enriquecer_municipios_dados_nfe(dados: dict[str, Any]) -> None:
    """
    Preenche c_mun do emitente (FG) e do destinatário antes da serialização XML.
    Destinatário nunca recebe cMunFG do emitente.
    """
    ide = dados.setdefault('ide', {})
    emit = dados.setdefault('emitente', {})
    dest = dados.setdefault('destinatario', {})

    c_fg = _digits(ide.get('c_mun_fg'), max_len=7) or _digits(emit.get('c_mun'), max_len=7)
    if not c_fg or c_fg == '3500000':
        c_fg = codigo_municipio_ibge(emit.get('uf'), cidade=emit.get('cidade'))
    ide['c_mun_fg'] = c_fg
    emit['c_mun'] = c_fg

    dest['c_mun'] = resolver_c_mun_destinatario(dest)
