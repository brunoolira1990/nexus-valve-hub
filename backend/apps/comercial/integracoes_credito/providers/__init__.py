"""Providers nulos/desabilitados — sem HTTP e sem dados fictícios."""

from __future__ import annotations

from apps.comercial.integracoes_credito.contratos import (
    ContextoConsulta,
    ProviderCapability,
    ResultadoBureauNormalizado,
    ResultadoCadastralNormalizado,
)
from apps.comercial.integracoes_credito.exceptions import (
    CODE_BURO_NAO_CONTRATADO,
    CODE_PROVIDER_NAO_CONFIGURADO,
    MSG_BURO_NAO_CONTRATADO,
    MSG_PROVIDER_GENERICO,
    IntegracaoCreditoError,
)


class ProviderCadastralNaoConfigurado:
    """Null/disabled cadastral — nunca consulta rede nem retorna empresa fictícia."""

    def nome_provider(self) -> str:
        return 'nao_configurado'

    def versao_contrato(self) -> str:
        return '0'

    def validar_configuracao(self) -> bool:
        return False

    def capability(self) -> ProviderCapability:
        return ProviderCapability(
            configurado=False,
            disponivel=False,
            provider=None,
            produto=None,
            permite_consulta=False,
            motivo=CODE_PROVIDER_NAO_CONFIGURADO,
            versao=None,
        )

    def consultar(self, cnpj: str, contexto: ContextoConsulta) -> ResultadoCadastralNormalizado:
        raise IntegracaoCreditoError(CODE_PROVIDER_NAO_CONFIGURADO, MSG_PROVIDER_GENERICO)


class ProviderBureauNaoContratado:
    """Null/disabled bureau — nunca consulta rede nem retorna score/dívidas."""

    def nome_provider(self) -> str:
        return 'nao_contratado'

    def versao_produto(self) -> str:
        return '0'

    def validar_configuracao(self) -> bool:
        return False

    def capability(self) -> ProviderCapability:
        return ProviderCapability(
            configurado=False,
            disponivel=False,
            provider=None,
            produto=None,
            permite_consulta=False,
            motivo=CODE_BURO_NAO_CONTRATADO,
            versao=None,
        )

    def consultar_empresa(
        self,
        cnpj: str,
        finalidade: str,
        id_solicitacao: str,
        contexto: ContextoConsulta,
    ) -> ResultadoBureauNormalizado:
        raise IntegracaoCreditoError(CODE_BURO_NAO_CONTRATADO, MSG_BURO_NAO_CONTRATADO)
