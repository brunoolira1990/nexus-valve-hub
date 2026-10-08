"""Texto de NF-e referenciada para infCpl / Informações Complementares do DANFE."""

from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import Element


def digits_chave_acesso(chave: str | None) -> str:
    return ''.join(c for c in (chave or '') if c.isdigit())


def formatar_chave_acesso_nfe(chave: str | None) -> str:
    digits = digits_chave_acesso(chave)
    if len(digits) != 44:
        return digits
    return ' '.join(digits[i : i + 4] for i in range(0, 44, 4))


def texto_documento_fiscal_referenciado(chave: str | None) -> str:
    """Linha padrão para Informações Complementares (devolução/ajuste)."""
    digits = digits_chave_acesso(chave)
    if len(digits) != 44:
        return ''
    return f'DOCUMENTO FISCAL REFERENCIADO: {formatar_chave_acesso_nfe(digits)}'


def chaves_ref_nfe_do_ide(ide: Element | None) -> list[str]:
    """Extrai chaves ``refNFe`` do grupo ide (ElementTree do BrazilFiscalReport)."""
    if ide is None:
        return []
    out: list[str] = []
    for el in ide.iter():
        tag = el.tag.rsplit('}', 1)[-1]
        if tag != 'refNFe':
            continue
        digits = digits_chave_acesso(el.text)
        if len(digits) == 44 and digits not in out:
            out.append(digits)
    return out


def anexar_referencias_ao_inf_cpl(obs: str, chaves: list[str]) -> str:
    """Garante que cada chave referenciada apareça no texto de Informações Complementares."""
    texto = (obs or '').strip()
    digits_obs = digits_chave_acesso(texto)
    for chave in chaves:
        linha = texto_documento_fiscal_referenciado(chave)
        if not linha:
            continue
        if chave in digits_obs:
            continue
        texto = f'{texto}\n{linha}'.strip() if texto else linha
        digits_obs = digits_chave_acesso(texto)
    return texto


def montar_inf_cpl_entrada_com_referencia(
    *,
    chave_nfe_referenciada: str | None = None,
    texto_base: str | None = None,
) -> str:
    base = (texto_base or '').strip()
    chaves = []
    digits = digits_chave_acesso(chave_nfe_referenciada)
    if len(digits) == 44:
        chaves.append(digits)
    return anexar_referencias_ao_inf_cpl(base, chaves)


def montar_inf_cpl_bindings_entrada(nfe_module: Any, inf_cpl: str) -> Any | None:
    texto = (inf_cpl or '').strip()
    if not texto:
        return None
    return nfe_module.Tnfe.InfNfe.InfAdic(infCpl=texto[:5000])
