"""Montagem do lote enviNFe 4.00 compacto (sem caracteres de edição — cStat 588)."""

from __future__ import annotations

from lxml import etree

from apps.fiscal.nfe_emissao.xml_compactacao import (
    XML_DECLARACAO,
    extrair_elemento_nfe,
    serializar_elemento_compacto,
)
from apps.fiscal.nfe_emissao.xml_serializacao import NFE_NS, _local_tag


def montar_envi_nfe_xml(
    xml_nfe_assinado: str,
    *,
    id_lote: int,
    ind_sinc: int = 1,
    versao: str = '4.00',
) -> str:
    """Envolve NF-e assinada em enviNFe compacto."""
    return montar_envi_nfe_compacto(
        xml_nfe_assinado,
        id_lote=id_lote,
        ind_sinc=ind_sinc,
        versao=versao,
    )


def montar_envi_nfe_compacto(
    xml_nfe_assinado: str | bytes,
    *,
    id_lote: int,
    ind_sinc: int = 1,
    versao: str = '4.00',
) -> str:
    """
    enviNFe sem indentação, BOM ou whitespace entre tags.
  """
    nfe_root = extrair_elemento_nfe(xml_nfe_assinado)

    envi = etree.Element(f'{{{NFE_NS}}}enviNFe', nsmap={None: NFE_NS})
    envi.set('versao', versao)

    id_lote_el = etree.SubElement(envi, f'{{{NFE_NS}}}idLote')
    id_lote_el.text = str(int(id_lote))

    ind_sinc_el = etree.SubElement(envi, f'{{{NFE_NS}}}indSinc')
    ind_sinc_el.text = str(int(ind_sinc))

    envi.append(nfe_root)

    body = serializar_elemento_compacto(envi, com_declaracao=False).decode('utf-8')
    return XML_DECLARACAO + body
