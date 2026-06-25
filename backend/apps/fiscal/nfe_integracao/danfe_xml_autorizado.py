"""Resolução do XML autorizado (procNFe) para DANFE e download."""

from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError

logger = logging.getLogger(__name__)

NS_NFE = 'http://www.portalfiscal.inf.br/nfe'

_CAMPOS_NFE = (
    'xml_assinado',
    'xml_nfe_gerado',
    'xml_envio_lote',
    'xml_envio',
    'xml_autorizado',
    'xml_retorno',
    'xml_retorno_lote',
)

_CAMPOS_PROTOCOLO = (
    'xml_protocolo',
    'xml_retorno',
    'xml_retorno_lote',
    'xml_autorizado',
)


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


def _parse_xml_root(texto: str) -> Any | None:
    from lxml import etree

    bruto = (texto or '').strip()
    if not bruto:
        return None
    bruto = re.sub(r'<\?xml[^?]*\?>\s*', '', bruto, count=1, flags=re.IGNORECASE)
    try:
        return etree.fromstring(bruto.encode('utf-8'))
    except Exception:
        return None


def _find_elemento(root: Any, local_name: str) -> Any | None:
    if root is None:
        return None
    if _local(root.tag) == local_name:
        return root
    for el in root.iter():
        if _local(el.tag) == local_name:
            return el
    return None


def _clone_elemento(el: Any) -> Any:
    from lxml import etree

    return etree.fromstring(etree.tostring(el, encoding='utf-8'))


def _montar_proc_nfe_elementos(nfe_el: Any, prot_el: Any) -> str:
    from apps.fiscal.nfe_emissao.retorno_sefaz import montar_proc_nfe_xml

    return montar_proc_nfe_xml(_clone_elemento(nfe_el), _clone_elemento(prot_el))


def _elemento_protocolo_nfe(protocolo: str) -> Any:
    root = _parse_xml_root(protocolo)
    if root is None:
        raise ValueError('XML de protocolo inválido.')
    prot = _find_elemento(root, 'protNFe')
    if prot is not None:
        return prot
    if _local(root.tag) == 'infProt':
        from lxml import etree

        wrapper = etree.Element(f'{{{NS_NFE}}}protNFe')
        wrapper.append(root)
        return wrapper
    raise ValueError('Elemento protNFe não encontrado no XML de protocolo.')


def _elemento_nfe(texto: str) -> Any | None:
    root = _parse_xml_root(texto)
    if root is None:
        return None
    return _find_elemento(root, 'NFe')


def _iter_textos_unicos(nf: NFeSaida, campos: tuple[str, ...]) -> Iterator[str]:
    vistos: set[str] = set()
    for campo in campos:
        texto = (getattr(nf, campo, None) or '').strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        yield texto


def _tentar_montar_proc_nfe(nfe_el: Any, protocolo_texto: str) -> str | None:
    try:
        prot_el = _elemento_protocolo_nfe(protocolo_texto)
        montado = _montar_proc_nfe_elementos(nfe_el, prot_el)
        if _xml_proc_nfe_completo(montado):
            return montado
    except Exception:
        return None
    return None


def _montar_xml_autorizado(nfe_saida: NFeSaida) -> str:
    xml_campo = (nfe_saida.xml_autorizado or '').strip()
    if xml_campo and _xml_proc_nfe_completo(xml_campo):
        return xml_campo

    for texto in _iter_textos_unicos(nfe_saida, _CAMPOS_NFE):
        if _xml_proc_nfe_completo(texto):
            return texto

    nfe_elementos: list[Any] = []
    for texto in _iter_textos_unicos(nfe_saida, _CAMPOS_NFE):
        nfe_el = _elemento_nfe(texto)
        if nfe_el is not None:
            nfe_elementos.append(nfe_el)

    if nfe_elementos:
        for nfe_el in nfe_elementos:
            for prot_texto in _iter_textos_unicos(nfe_saida, _CAMPOS_PROTOCOLO):
                montado = _tentar_montar_proc_nfe(nfe_el, prot_texto)
                if montado:
                    return montado

    raise DanfeBfrError(
        'XML autorizado não disponível. '
        'Verifique se o XML assinado e o protocolo SEFAZ estão gravados nesta NF-e.',
    )


def extrair_nfe_xml_para_bfr(xml: str) -> str | None:
    """Extrai só o bloco NFe quando procNFe completo falhar no renderizador."""
    nfe_el = _elemento_nfe(xml)
    if nfe_el is None:
        return None
    from lxml import etree

    corpo = etree.tostring(nfe_el, encoding='unicode', xml_declaration=False)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{corpo}'


def resolver_xml_autorizado_danfe(nfe_saida: NFeSaida, *, persistir: bool = False) -> str:
    """
    Retorna procNFe/XML autorizado para renderização do DANFE final.

    Com ``persistir=True``, grava ``xml_autorizado`` quando montado ou corrigido.
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
