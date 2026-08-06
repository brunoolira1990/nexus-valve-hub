"""Geração de PDF (DANFE/DACTE) a partir de XML armazenado em documentos recebidos."""

from __future__ import annotations

import logging
import re

from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    DanfeBfrError,
    gerar_danfe_bfr_de_xml_string,
)

logger = logging.getLogger(__name__)


class DocumentoRecebidoPdfError(ValueError):
    """Erro amigável na geração de PDF de documento recebido."""


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
    """Gera DACTE (Nexus/ReportLab) a partir do XML armazenado em CTeHistoricoImportado."""
    from apps.fiscal.dacte_nexus import gerar_dacte_nexus_pdf

    xml_limpo = _sanitizar_xml_texto(xml)
    try:
        pdf = gerar_dacte_nexus_pdf(xml_limpo)
    except DocumentoRecebidoPdfError:
        raise
    except ValueError as exc:
        raise DocumentoRecebidoPdfError(str(exc)) from exc
    except Exception as exc:
        logger.warning('Falha ao gerar DACTE de CT-e: %s', type(exc).__name__)
        raise DocumentoRecebidoPdfError(
            'Não foi possível gerar o DACTE a partir do XML armazenado.',
        ) from exc
    if not pdf or not pdf.startswith(b'%PDF'):
        raise DocumentoRecebidoPdfError('O PDF do DACTE retornado está vazio ou inválido.')
    return pdf
