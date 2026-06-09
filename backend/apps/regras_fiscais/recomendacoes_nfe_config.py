"""Chaves e helpers para recomendacoes_nfe (JSON) em RegraFiscalSaida."""

from __future__ import annotations

from typing import Any

RECOMENDACOES_NFE_KEYS = (
    'danfe_paisagem',
    'nao_preencher_data_hora_saida',
    'ocultar_destaque_pis_cofins',
    'ocultar_destaque_icms_st_itens',
    'ordenar_itens_por_descricao',
    'exibir_email_destinatario',
    'exibir_cest_informacoes_item',
    'exibir_pedido_compra_item',
    'exibir_chave_dfe_referenciado',
    'emitir_etiqueta_danfe_simplificado',
    'enviar_retencoes_como_desconto',
)


def normalizar_recomendacoes_nfe(data: Any) -> dict[str, bool] | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, bool] = {}
    for key in RECOMENDACOES_NFE_KEYS:
        if key not in data:
            continue
        out[key] = bool(data[key])
    return out or None


def recomendacoes_nfe_preenchidas(data: Any) -> bool:
    norm = normalizar_recomendacoes_nfe(data)
    if not norm:
        return False
    return any(norm.values())


def contar_recomendacoes_nfe(data: Any) -> int:
    norm = normalizar_recomendacoes_nfe(data)
    if not norm:
        return 0
    return sum(1 for v in norm.values() if v)
