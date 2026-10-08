"""Serviço de consultas externas — fundação desabilitada (sem HTTP)."""

from __future__ import annotations

from typing import Any

from apps.comercial.integracoes_credito.contratos import ContextoConsulta
from apps.comercial.integracoes_credito.exceptions import (
    CODE_BURO_NAO_CONTRATADO,
    CODE_CONSULTA_DESABILITADA,
    CODE_PROVIDER_NAO_CONFIGURADO,
    MSG_BURO_NAO_CONTRATADO,
    MSG_CADASTRAL_NAO_CONFIGURADO,
    IntegracaoCreditoError,
)
from apps.comercial.integracoes_credito.registry import get_default_registry


def tentar_consulta_cadastral(*, cnpj: str, analise_id: int | None = None) -> None:
    """
    Tentativa explícita de consulta cadastral.

    Nesta fundação:
    - falha antes de qualquer rede;
    - não cria ConsultaExternaAnaliseFinanceira (nenhum status);
    - não registra evento de análise;
    - não altera AnaliseFinanceiraProposta.
    """
    reg = get_default_registry()
    provider = reg.provider_cadastral_efetivo()
    cap = provider.capability()
    if not cap.configurado or not cap.permite_consulta:
        raise IntegracaoCreditoError(CODE_PROVIDER_NAO_CONFIGURADO, MSG_CADASTRAL_NAO_CONFIGURADO)
    # Sem provider real registrado como ativo: caminho acima sempre dispara.
    # Se um fake de teste estiver ativo, ainda bloqueamos escrita operacional na fundação.
    raise IntegracaoCreditoError(
        CODE_CONSULTA_DESABILITADA,
        'A consulta cadastral operacional ainda não está habilitada nesta versão.',
    )


def tentar_consulta_buro(
    *,
    cnpj: str,
    finalidade: str = '',
    id_solicitacao: str = '',
    analise_id: int | None = None,
) -> None:
    """
    Tentativa explícita de birô.

    Nesta fundação: 409 de negócio sem persistência, sem evento e sem custo.
    """
    reg = get_default_registry()
    provider = reg.provider_bureau_efetivo()
    cap = provider.capability()
    if not cap.configurado or not cap.permite_consulta:
        raise IntegracaoCreditoError(CODE_BURO_NAO_CONTRATADO, MSG_BURO_NAO_CONTRATADO)
    raise IntegracaoCreditoError(
        CODE_CONSULTA_DESABILITADA,
        'A consulta de birô operacional ainda não está habilitada nesta versão.',
    )


def executar_provider_cadastral_somente_teste(cnpj: str) -> Any:
    """Helper de teste: chama o provider efetivo (nulo lança IntegracaoCreditoError)."""
    return get_default_registry().provider_cadastral_efetivo().consultar(
        cnpj, ContextoConsulta()
    )


def executar_provider_buro_somente_teste(cnpj: str) -> Any:
    return get_default_registry().provider_bureau_efetivo().consultar_empresa(
        cnpj, 'credito', 'test', ContextoConsulta()
    )
