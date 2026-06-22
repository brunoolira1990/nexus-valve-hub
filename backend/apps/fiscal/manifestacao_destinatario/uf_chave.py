"""UF autorizadora da NF-e a partir da chave de acesso (cUF)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from apps.fiscal.nfe_saida_preview import UF_IBGE

IBGE_PARA_UF: dict[str, str] = {codigo: uf for uf, codigo in UF_IBGE.items()}

MSG_CHAVE_UF_INVALIDA = 'Chave de acesso inválida para identificar a UF autorizadora.'


def _normalizar_chave(chave_acesso: str) -> str:
    return ''.join(c for c in (chave_acesso or '').strip() if c.isdigit())


def validar_chave_nfe_manifestacao(chave_acesso: str) -> str:
    chave = _normalizar_chave(chave_acesso)
    if len(chave) != 44:
        raise ValueError(MSG_CHAVE_UF_INVALIDA)
    return chave


def corgao_ibge_por_chave(chave_acesso: str) -> str:
    """cUF/cOrgao SEFAZ — dois primeiros dígitos da chave (ex.: 35 = SP)."""
    chave = validar_chave_nfe_manifestacao(chave_acesso)
    corgao = chave[:2]
    if corgao not in IBGE_PARA_UF:
        raise ValueError(f'cUF {corgao} da chave não reconhecido para manifestação.')
    return corgao


def uf_autorizadora_por_chave(chave_acesso: str) -> str:
    """
    Retorna a sigla da UF autorizadora (cUF) com base nos 2 primeiros dígitos da chave.

    Manifestação do destinatário exige cOrgao alinhado ao órgão autorizador da NF-e.
    Usar empresa.uf pode gerar cStat 657 quando a NF-e é de outra UF.
    """
    corgao = corgao_ibge_por_chave(chave_acesso)
    return IBGE_PARA_UF[corgao]


def aplicar_corgao_evento_manifestacao(xml_evento: ET.Element, corgao: str) -> ET.Element:
    """Garante cOrgao do infEvento alinhado ao cUF da chave (evita cStat 657)."""
    corgao = (corgao or '').strip()
    if len(corgao) != 2 or not corgao.isdigit():
        raise ValueError('cOrgao inválido para evento de manifestação.')
    for el in xml_evento.iter():
        if el.tag.split('}')[-1] == 'cOrgao':
            el.text = corgao
            return xml_evento
    raise ValueError('Elemento cOrgao não encontrado no XML do evento de manifestação.')
