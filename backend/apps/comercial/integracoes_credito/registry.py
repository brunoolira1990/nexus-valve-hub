"""Registry explícito de providers — inicia vazio (sem adapters reais)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.comercial.integracoes_credito.exceptions import (
    CODE_PROVIDER_DESCONHECIDO,
    IntegracaoCreditoError,
)
from apps.comercial.integracoes_credito.providers import (
    ProviderBureauNaoContratado,
    ProviderCadastralNaoConfigurado,
)

if TYPE_CHECKING:
    from apps.comercial.integracoes_credito.contratos import (
        ConsultaCadastralCNPJProvider,
        CreditBureauProvider,
    )


class CreditIntegrationRegistry:
    """
    Resolve providers somente por nome reconhecido.

    Produção inicia sem cadastral/birô reais. Fakes só via injeção em testes.
    Sem fallback para ReceitaWS ou mock.
    """

    def __init__(self) -> None:
        self._cadastral: dict[str, ConsultaCadastralCNPJProvider] = {}
        self._bureau: dict[str, CreditBureauProvider] = {}
        self._cadastral_ativo: str | None = None
        self._bureau_ativo: str | None = None
        self._null_cadastral = ProviderCadastralNaoConfigurado()
        self._null_bureau = ProviderBureauNaoContratado()

    def register_cadastral(self, nome: str, provider: ConsultaCadastralCNPJProvider, *, ativo: bool = False) -> None:
        key = (nome or '').strip().lower()
        if not key or key in {'nao_configurado', 'null', 'disabled', 'mock', 'fake', 'receitaws'}:
            raise IntegracaoCreditoError(
                CODE_PROVIDER_DESCONHECIDO,
                'Nome de provider cadastral não permitido neste registry.',
            )
        self._cadastral[key] = provider
        if ativo:
            self._cadastral_ativo = key

    def register_bureau(self, nome: str, provider: CreditBureauProvider, *, ativo: bool = False) -> None:
        key = (nome or '').strip().lower()
        if not key or key in {'nao_contratado', 'null', 'disabled', 'mock', 'fake'}:
            raise IntegracaoCreditoError(
                CODE_PROVIDER_DESCONHECIDO,
                'Nome de provider de birô não permitido neste registry.',
            )
        self._bureau[key] = provider
        if ativo:
            self._bureau_ativo = key

    def clear(self) -> None:
        self._cadastral.clear()
        self._bureau.clear()
        self._cadastral_ativo = None
        self._bureau_ativo = None

    def resolver_cadastral(self, nome: str | None = None) -> ConsultaCadastralCNPJProvider:
        if nome is None:
            if self._cadastral_ativo and self._cadastral_ativo in self._cadastral:
                return self._cadastral[self._cadastral_ativo]
            return self._null_cadastral
        key = nome.strip().lower()
        if key not in self._cadastral:
            raise IntegracaoCreditoError(
                CODE_PROVIDER_DESCONHECIDO,
                'Provider cadastral desconhecido ou não registrado.',
            )
        return self._cadastral[key]

    def resolver_bureau(self, nome: str | None = None) -> CreditBureauProvider:
        if nome is None:
            if self._bureau_ativo and self._bureau_ativo in self._bureau:
                return self._bureau[self._bureau_ativo]
            return self._null_bureau
        key = nome.strip().lower()
        if key not in self._bureau:
            raise IntegracaoCreditoError(
                CODE_PROVIDER_DESCONHECIDO,
                'Provider de birô desconhecido ou não registrado.',
            )
        return self._bureau[key]

    def provider_cadastral_efetivo(self) -> ConsultaCadastralCNPJProvider:
        return self.resolver_cadastral(None)

    def provider_bureau_efetivo(self) -> CreditBureauProvider:
        return self.resolver_bureau(None)


_DEFAULT_REGISTRY = CreditIntegrationRegistry()


def get_default_registry() -> CreditIntegrationRegistry:
    return _DEFAULT_REGISTRY


def reset_default_registry_for_tests() -> CreditIntegrationRegistry:
    """Somente testes: limpa injeções."""
    _DEFAULT_REGISTRY.clear()
    return _DEFAULT_REGISTRY
