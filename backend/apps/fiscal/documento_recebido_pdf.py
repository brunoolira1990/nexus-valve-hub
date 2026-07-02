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


def _normalizar_xml_cte_para_dacte(xml: str) -> str:
    """
    BrazilFiscalReport Dacte espera o elemento infCte como raiz do XML informado.
    Aceita XML armazenado como infCte, CTe ou cteProc.
    """
    xml_limpo = _sanitizar_xml_texto(xml)
    try:
        root = ET.fromstring(xml_limpo)
    except ET.ParseError as exc:
        raise DocumentoRecebidoPdfError('XML de CT-e inválido ou malformado.') from exc

    root_name = _local_tag(root.tag)
    inf_cte: ET.Element | None
    if root_name == 'infCte':
        inf_cte = root
    elif root_name == 'CTe':
        inf_cte = _find_child(root, 'infCte')
    elif root_name == 'cteProc':
        cte = _find_child(root, 'CTe')
        inf_cte = _find_child(cte, 'infCte') if cte is not None else None
    else:
        inf_cte = None

    if inf_cte is None:
        raise DocumentoRecebidoPdfError(
            'XML de CT-e incompleto: não foi possível localizar o bloco infCte.',
        )
    return ET.tostring(inf_cte, encoding='unicode')


def _importar_dacte():
    try:
        from brazilfiscalreport.dacte import Dacte
        from brazilfiscalreport.dacte.config import DacteConfig
    except ImportError as exc:
        raise DacteBfrIndisponivelError(
            'Geração de DACTE indisponível: BrazilFiscalReport ou dependência (qrcode) não instalada.',
        ) from exc
    return Dacte, DacteConfig


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
    xml_inf_cte = _normalizar_xml_cte_para_dacte(xml)
    try:
        dacte = Dacte(xml=xml_inf_cte, config=DacteConfig())
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
