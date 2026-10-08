"""UF/cUF da chave NF-e e parâmetros do Ambiente Nacional para manifestação."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from apps.fiscal.nfe_saida_preview import UF_IBGE

IBGE_PARA_UF: dict[str, str] = {codigo: uf for uf, codigo in UF_IBGE.items()}

MSG_CHAVE_UF_INVALIDA = 'Chave de acesso inválida para identificar a UF autorizadora.'

# Manifestação do Destinatário é recepcionada pelo Ambiente Nacional (NT 2014.002 / NFe_Util siglaWS=AN).
CORGAO_MANIFESTACAO_DESTINATARIO = '91'
UF_SERVICO_MANIFESTACAO = 'AN'


def _normalizar_chave(chave_acesso: str) -> str:
    return ''.join(c for c in (chave_acesso or '').strip() if c.isdigit())


def validar_chave_nfe_manifestacao(chave_acesso: str) -> str:
    chave = _normalizar_chave(chave_acesso)
    if len(chave) != 44:
        raise ValueError(MSG_CHAVE_UF_INVALIDA)
    return chave


def chave_prefixo_uf(chave_acesso: str) -> str:
    """Dois primeiros dígitos da chave (cUF autorizador da NF-e) — apenas diagnóstico."""
    chave = validar_chave_nfe_manifestacao(chave_acesso)
    return chave[:2]


def corgao_ibge_por_chave(chave_acesso: str) -> str:
    """cUF da NF-e (autorizador) — não confundir com cOrgao do evento de manifestação (91=AN)."""
    corgao = chave_prefixo_uf(chave_acesso)
    if corgao not in IBGE_PARA_UF:
        raise ValueError(f'cUF {corgao} da chave não reconhecido para manifestação.')
    return corgao


def uf_autorizadora_por_chave(chave_acesso: str) -> str:
    """Sigla da UF autorizadora da NF-e (cUF nos 2 primeiros dígitos da chave)."""
    corgao = corgao_ibge_por_chave(chave_acesso)
    return IBGE_PARA_UF[corgao]


def _tag_local(tag: str) -> str:
    return tag.split('}')[-1]


def extrair_corgao_xml_evento(xml_evento: ET.Element) -> str:
    for el in xml_evento.iter():
        if _tag_local(el.tag) == 'cOrgao':
            return (el.text or '').strip()
    return ''


def extrair_tp_evento_xml_evento(xml_evento: ET.Element) -> str:
    for el in xml_evento.iter():
        if _tag_local(el.tag) == 'tpEvento':
            return (el.text or '').strip()
    return ''


def garantir_corgao_ambiente_nacional(xml_evento: ET.Element) -> ET.Element:
    """Garante cOrgao=91 no infEvento (PyNFe já usa AN; reforço defensivo antes da assinatura)."""
    corgao = CORGAO_MANIFESTACAO_DESTINATARIO
    for el in xml_evento.iter():
        if _tag_local(el.tag) == 'cOrgao':
            el.text = corgao
            return xml_evento
    raise ValueError('Elemento cOrgao não encontrado no XML do evento de manifestação.')
