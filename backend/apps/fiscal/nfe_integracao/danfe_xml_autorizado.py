"""Resolução read-only do XML autorizado (procNFe) para DANFE — sem alterar persistência."""

from __future__ import annotations

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError


def _xml_tem_protocolo(xml: str) -> bool:
    import re

    return bool(re.search(r'<[\w:]*protNFe\b', xml, flags=re.IGNORECASE))


def resolver_xml_autorizado_danfe(nfe_saida: NFeSaida) -> str:
    """
    Retorna procNFe/XML autorizado para renderização do DANFE final.
    Não grava nem altera campos da NF-e.
    """
    xml = (nfe_saida.xml_autorizado or '').strip()
    if xml:
        return xml

    assinado = (nfe_saida.xml_assinado or nfe_saida.xml_nfe_gerado or '').strip()
    protocolo = (nfe_saida.xml_protocolo or '').strip()
    if assinado and protocolo:
        try:
            from lxml import etree

            from apps.fiscal.nfe_emissao.retorno_sefaz import _montar_proc_nfe_de_assinado

            prot_el = etree.fromstring(protocolo.encode('utf-8'))
            return _montar_proc_nfe_de_assinado(assinado, prot_el)
        except Exception as exc:
            raise DanfeBfrError(
                'Não foi possível montar XML autorizado a partir do protocolo SEFAZ.',
            ) from exc

    for candidato in (
        nfe_saida.xml_retorno or '',
        nfe_saida.xml_retorno_lote or '',
    ):
        texto = (candidato or '').strip()
        if texto and _xml_tem_protocolo(texto) and '<NFe' in texto:
            return texto

    raise DanfeBfrError(
        'XML autorizado não disponível. Baixe o XML autorizado antes de gerar o DANFE.',
    )
