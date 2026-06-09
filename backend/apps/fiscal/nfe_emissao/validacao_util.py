"""Utilitários compartilhados de validação NF-e emissão."""

from __future__ import annotations

from typing import Any

from apps.fiscal.validacao_nfe_saida import TIPO_PENDENCIA


def extrair_mensagens_pendencias_validacao(val: dict[str, Any]) -> list[str]:
    """Extrai mensagens de pendências bloqueantes do payload de validar_nfe_saida_para_emissao."""
    msgs: list[str] = []
    for grupo_itens in (val.get('grupos') or {}).values():
        for it in grupo_itens:
            if it.get('tipo') != TIPO_PENDENCIA:
                continue
            m = (it.get('mensagem') or '').strip()
            if m:
                msgs.append(m)
    return msgs
