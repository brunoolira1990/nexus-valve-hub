"""
CSTs da NF-e para exibição na conferência de entrada (perspectiva do destinatário).

Converte os códigos lidos do XML (saída do fornecedor) antes de mostrar ao operador.
Não altera validação fiscal — uso exclusivo de UI.
"""

from __future__ import annotations

from typing import Any

from apps.regras_fiscais.cst_icms_perspectiva import (
    normalizar_cst_icms_xml_para_entrada,
    obter_cst_icms_bruto_nf,
)
from apps.regras_fiscais.cst_ipi_perspectiva import normalizar_cst_ipi_xml_para_entrada
from apps.regras_fiscais.cst_pis_cofins_perspectiva import normalizar_cst_pis_cofins_xml_para_entrada


def tributos_nf_para_exibicao_entrada(trib: dict[str, Any]) -> dict[str, str]:
    """Retorna CSTs normalizados para entrada; CSOSN permanece quando CST veio do XML."""
    cst_icms_nf = str(trib.get('cst_icms') or '').strip()
    csosn_nf = str(trib.get('csosn') or '').strip()
    cst_bruto = obter_cst_icms_bruto_nf(trib)
    cst_exib = normalizar_cst_icms_xml_para_entrada(cst_bruto) if cst_bruto else ''
    cst_ipi_nf = str(trib.get('cst_ipi') or '').strip()
    cst_pis_nf = str(trib.get('cst_pis') or '').strip()
    cst_cofins_nf = str(trib.get('cst_cofins') or '').strip()

    return {
        'cst_icms': cst_exib,
        'csosn': csosn_nf if cst_icms_nf else '',
        'cst_ipi': normalizar_cst_ipi_xml_para_entrada(cst_ipi_nf) if cst_ipi_nf else '',
        'cst_pis': normalizar_cst_pis_cofins_xml_para_entrada(cst_pis_nf) if cst_pis_nf else '',
        'cst_cofins': normalizar_cst_pis_cofins_xml_para_entrada(cst_cofins_nf) if cst_cofins_nf else '',
    }
