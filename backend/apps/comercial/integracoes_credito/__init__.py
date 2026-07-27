"""Fundação B2/B3 — consultas externas da Liberação Financeira.

Providers reais ausentes nesta fase. Sem HTTP externo. Sem dados simulados em produção.
"""

from apps.comercial.integracoes_credito.capabilities import montar_capability_integracoes
from apps.comercial.integracoes_credito.exceptions import IntegracaoCreditoError
from apps.comercial.integracoes_credito.registry import CreditIntegrationRegistry

__all__ = [
    'CreditIntegrationRegistry',
    'IntegracaoCreditoError',
    'montar_capability_integracoes',
]
