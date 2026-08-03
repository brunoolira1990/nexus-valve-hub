"""Logo do emitente para DANFE (BrazilFiscalReport)."""

from __future__ import annotations

import logging
import os

from apps.cadastros.models import Empresa

logger = logging.getLogger(__name__)


def get_empresa_logo_path_or_none(empresa: Empresa | None) -> str | None:
    """
    Caminho local do logotipo para DanfeConfig.logo (path absoluto).

    Retorna None se ausente, inválido ou inacessível — a DANFE segue sem logo.
    """
    if not empresa:
        return None
    try:
        field = getattr(empresa, 'logotipo', None)
        if not field:
            return None
        path = getattr(field, 'path', None)
        if path and os.path.isfile(path):
            return path
    except Exception as exc:
        logger.debug('logo empresa id=%s: %s', getattr(empresa, 'pk', None), exc)
    return None


def get_emitente_logo_nfe_saida(nfe_saida) -> str | None:
    """Logo da empresa emitente vinculada ao pedido da NF-e."""
    try:
        pedido = getattr(nfe_saida, 'pedido_venda', None)
        emp = getattr(pedido, 'empresa_emitente', None) if pedido else None
        return get_empresa_logo_path_or_none(emp)
    except Exception as exc:
        logger.debug('logo NF-e %s: %s', getattr(nfe_saida, 'pk', None), exc)
        return None


def get_emitente_logo_nfe_entrada(nfe_entrada) -> str | None:
    """Logo da empresa emitente da NF-e de entrada própria."""
    try:
        return get_empresa_logo_path_or_none(getattr(nfe_entrada, 'empresa_emitente', None))
    except Exception as exc:
        logger.debug('logo NF-e entrada %s: %s', getattr(nfe_entrada, 'pk', None), exc)
        return None
