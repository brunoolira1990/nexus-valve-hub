"""Capability pública das integrações — sem secrets e sem HTTP."""

from __future__ import annotations

from typing import Any

from apps.comercial.integracoes_credito.exceptions import (
    CODE_BURO_NAO_CONTRATADO,
    CODE_PROVIDER_NAO_CONFIGURADO,
)
from apps.comercial.integracoes_credito.registry import CreditIntegrationRegistry, get_default_registry


def _capability_dict(*, configurado: bool, disponivel: bool, motivo: str, provider=None, produto=None) -> dict[str, Any]:
    return {
        'configurado': configurado,
        'disponivel': disponivel,
        'provider': provider if configurado else None,
        'produto': produto if configurado else None,
        'permite_consulta': bool(configurado and disponivel),
        'motivo': motivo,
    }


def montar_capability_integracoes(registry: CreditIntegrationRegistry | None = None) -> dict[str, Any]:
    """
    Monta capability sem chamar providers remotos e sem ler secrets.

    Com registry vazio (produção nesta fundação), retorna desabilitado.
    """
    reg = registry or get_default_registry()
    cadastral = reg.provider_cadastral_efetivo()
    bureau = reg.provider_bureau_efetivo()

    # Nunca chamar consultar(); apenas capability() local do provider efetivo.
    cap_c = cadastral.capability()
    cap_b = bureau.capability()

    return {
        'cadastral': _capability_dict(
            configurado=cap_c.configurado,
            disponivel=cap_c.disponivel,
            motivo=cap_c.motivo or CODE_PROVIDER_NAO_CONFIGURADO,
            provider=cap_c.provider,
            produto=cap_c.produto,
        ),
        'buro': _capability_dict(
            configurado=cap_b.configurado,
            disponivel=cap_b.disponivel,
            motivo=cap_b.motivo or CODE_BURO_NAO_CONTRATADO,
            provider=cap_b.provider,
            produto=cap_b.produto,
        ),
        'decisao_financeira': 'MANUAL',
    }
