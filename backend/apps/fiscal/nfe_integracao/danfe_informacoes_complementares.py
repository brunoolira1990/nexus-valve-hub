"""Compat — use ``danfe_xml_adicionais``."""

from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (  # noqa: F401
    deduplicar_textos_inf_cpl,
    montar_inf_ad_prod_item,
    montar_inf_cpl_nfe,
    montar_informacoes_complementares_danfe,
)
