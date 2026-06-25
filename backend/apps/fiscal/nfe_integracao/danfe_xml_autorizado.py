"""Resolução do XML autorizado (procNFe) para DANFE e download."""

from __future__ import annotations

import logging
import re

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError

logger = logging.getLogger(__name__)

NS_NFE = 'http://www.portalfiscal.inf.br/nfe'


def _local(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _xml_tem_protocolo(xml: str) -> bool:
    return bool(re.search(r'<[\w:]*protNFe\b', xml, flags=re.IGNORECASE))


def _xml_proc_nfe_completo(xml: str) -> bool:
    """procNFe válido para BFR — exige corpo NFe/infNFe e protocolo."""
    texto = (xml or '').strip()
    if not texto:
        return False
    if not _xml_tem_protocolo(texto):
        return False
    if not re.search(r'<[\w:]*NFe\b', texto, flags=re.IGNORECASE):
        return False
    return 'infNFe' in texto


def _elemento_protocolo_nfe(protocolo: str):
    from lxml import etree

    root = etree.fromstring(protocolo.encode('utf-8'))
    if _local(root.tag) == 'protNFe':
        return root
    if _local(root.tag) == 'infProt':
        wrapper = etree.Element(f'{{{NS_NFE}}}protNFe')
        wrapper.append(root)
        return wrapper
    for el in root.iter():
        if _local(el.tag) == 'protNFe':
            return el
    raise ValueError('Elemento protNFe não encontrado no XML de protocolo.')


def _montar_xml_autorizado(nfe_saida: NFeSaida) -> str:
    xml_campo = (nfe_saida.xml_autorizado or '').strip()
    if xml_campo and _xml_proc_nfe_completo(xml_campo):
        return xml_campo

    assinado = (nfe_saida.xml_assinado or nfe_saida.xml_nfe_gerado or '').strip()
    protocolo = (nfe_saida.xml_protocolo or '').strip()
    if assinado and protocolo:
        try:
            from apps.fiscal.nfe_emissao.retorno_sefaz import _montar_proc_nfe_de_assinado

            prot_el = _elemento_protocolo_nfe(protocolo)
            montado = _montar_proc_nfe_de_assinado(assinado, prot_el)
            if _xml_proc_nfe_completo(montado):
                return montado
        except Exception as exc:
            raise DanfeBfrError(
                'Não foi possível montar XML autorizado a partir do protocolo SEFAZ.',
            ) from exc

    if xml_campo and _xml_proc_nfe_completo(xml_campo):
        return xml_campo

    for candidato in (
        nfe_saida.xml_retorno or '',
        nfe_saida.xml_retorno_lote or '',
    ):
        texto = (candidato or '').strip()
        if texto and _xml_proc_nfe_completo(texto):
            return texto

    raise DanfeBfrError(
        'XML autorizado não disponível. Baixe o XML autorizado antes de gerar o DANFE.',
    )


def resolver_xml_autorizado_danfe(nfe_saida: NFeSaida, *, persistir: bool = False) -> str:
    """
    Retorna procNFe/XML autorizado para renderização do DANFE final.

    Com ``persistir=True``, grava ``xml_autorizado`` quando montado ou corrigido
    (ex.: campo continha só protNFe sem o corpo da NF-e).
    """
    xml = _montar_xml_autorizado(nfe_saida)
    xml_campo = (nfe_saida.xml_autorizado or '').strip()
    if persistir and xml.strip() and xml.strip() != xml_campo:
        try:
            nfe_saida.xml_autorizado = xml
            nfe_saida.save(update_fields=['xml_autorizado'])
        except Exception:
            logger.exception(
                'Falha ao persistir xml_autorizado nfe_id=%s — DANFE segue com XML montado.',
                nfe_saida.pk,
            )
    return xml
