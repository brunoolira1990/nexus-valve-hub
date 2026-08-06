"""Geração de PDF (DANFE/DACTE) a partir de XML armazenado em documentos recebidos."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from io import BytesIO

from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    DanfeBfrError,
    gerar_danfe_bfr_de_xml_string,
)

logger = logging.getLogger(__name__)


class DocumentoRecebidoPdfError(ValueError):
    """Erro amigável na geração de PDF de documento recebido."""


class DacteBfrIndisponivelError(DocumentoRecebidoPdfError):
    """BrazilFiscalReport DACTE ou dependência ausente."""


def _local_tag(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _find_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in parent:
        if _local_tag(child.tag) == name:
            return child
    return None


def _sanitizar_xml_texto(xml: str) -> str:
    texto = str(xml or '')
    texto = re.sub(r'<!--.*?-->', '', texto, flags=re.DOTALL)
    texto = re.sub(r'<\?xml[^?]*\?>\s*', '', texto, flags=re.IGNORECASE)
    texto = texto.strip()
    if not texto:
        raise DocumentoRecebidoPdfError('XML completo não armazenado para este documento.')
    if not texto.startswith('<'):
        raise DocumentoRecebidoPdfError('XML inválido: conteúdo não parece um documento fiscal.')
    return texto


_CTE_NS = 'http://www.portalfiscal.inf.br/cte'


def _localizar_inf_cte(root: ET.Element) -> ET.Element | None:
    root_name = _local_tag(root.tag)
    if root_name == 'infCte':
        return root
    if root_name == 'CTe':
        return _find_child(root, 'infCte')
    if root_name == 'cteProc':
        cte = _find_child(root, 'CTe')
        return _find_child(cte, 'infCte') if cte is not None else None
    for el in root.iter():
        if _local_tag(el.tag) == 'infCte':
            return el
    return None


def _normalizar_xml_cte_para_dacte(xml: str) -> str:
    """
    Prepara o XML para BrazilFiscalReport Dacte.

    O BFR localiza nós com ``.//{ns}infCte`` (descendente). Se a raiz for o próprio
    ``infCte``, ``find`` retorna None e a geração quebra com AttributeError.
    Por isso preferimos ``cteProc`` / ``CTe`` intactos; só embrulhamos ``infCte`` solto.
    """
    xml_limpo = _sanitizar_xml_texto(xml)
    try:
        root = ET.fromstring(xml_limpo)
    except ET.ParseError as exc:
        raise DocumentoRecebidoPdfError('XML de CT-e inválido ou malformado.') from exc

    inf_cte = _localizar_inf_cte(root)
    if inf_cte is None:
        raise DocumentoRecebidoPdfError(
            'XML de CT-e incompleto: não foi possível localizar o bloco infCte.',
        )

    root_name = _local_tag(root.tag)
    if root_name in {'cteProc', 'CTe'}:
        return xml_limpo
    if root_name == 'infCte':
        return (
            f'<CTe xmlns="{_CTE_NS}">'
            f'{ET.tostring(inf_cte, encoding="unicode")}'
            f'</CTe>'
        )
    return xml_limpo


def _importar_dacte():
    try:
        from brazilfiscalreport.dacte import Dacte
        from brazilfiscalreport.dacte.config import DacteConfig
    except ImportError as exc:
        raise DacteBfrIndisponivelError(
            'Geração de DACTE indisponível: BrazilFiscalReport ou dependência (qrcode) não instalada.',
        ) from exc
    return Dacte, DacteConfig


def _classe_dacte_nexus(Dacte):
    """Subclasse BFR que corrige sobreposição do nome do emitente com o CNPJ."""

    from apps.fiscal.dacte_bfr_emit import patch_draw_header_emitente

    class DacteNexus(Dacte):
        def _draw_header(self):
            patch_draw_header_emitente(self, lambda d: Dacte._draw_header(d))

    return DacteNexus


def gerar_danfe_nfe_entrada_historica(xml: str) -> bytes:
    """Gera DANFE a partir do XML armazenado em NFeEntradaHistoricaImportada."""
    xml_limpo = _sanitizar_xml_texto(xml)
    try:
        pdf = gerar_danfe_bfr_de_xml_string(xml_limpo)
    except DanfeBfrError as exc:
        raise DocumentoRecebidoPdfError(str(exc)) from exc
    except Exception as exc:
        logger.warning('Falha ao gerar DANFE de NF-e entrada: %s', type(exc).__name__)
        raise DocumentoRecebidoPdfError(
            'Não foi possível gerar o DANFE a partir do XML armazenado.',
        ) from exc
    if not pdf or not pdf.startswith(b'%PDF'):
        raise DocumentoRecebidoPdfError('O PDF do DANFE retornado está vazio ou inválido.')
    return pdf


def gerar_dacte_cte_historico(xml: str) -> bytes:
    """Gera DACTE a partir do XML armazenado em CTeHistoricoImportado."""
    Dacte, DacteConfig = _importar_dacte()
    DacteNexus = _classe_dacte_nexus(Dacte)
    xml_para_dacte = _normalizar_xml_cte_para_dacte(xml)
    try:
        dacte = DacteNexus(xml=xml_para_dacte, config=DacteConfig())
        buffer = BytesIO()
        dacte.output(buffer)
        pdf = buffer.getvalue()
    except DocumentoRecebidoPdfError:
        raise
    except Exception as exc:
        logger.warning('Falha ao gerar DACTE de CT-e: %s', type(exc).__name__)
        raise DocumentoRecebidoPdfError(
            'Não foi possível gerar o DACTE a partir do XML armazenado.',
        ) from exc
    if not pdf or not pdf.startswith(b'%PDF'):
        raise DocumentoRecebidoPdfError('O PDF do DACTE retornado está vazio ou inválido.')
    return pdf
