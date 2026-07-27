"""Contratos (interfaces) de providers — sem HTTP e sem acoplamento a fornecedores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderCapability:
    configurado: bool
    disponivel: bool
    provider: str | None
    produto: str | None
    permite_consulta: bool
    motivo: str
    versao: str | None = None


@dataclass(frozen=True)
class ContextoConsulta:
    """Contexto mínimo — sem models ORM."""

    analise_id: int | None = None
    finalidade: str | None = None
    id_solicitacao: str | None = None
    metadados: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CnaeNormalizado:
    codigo: str
    descricao: str | None = None


@dataclass(frozen=True)
class ResultadoCadastralNormalizado:
    """DTO interno — não serializar raw de provider."""

    provider: str
    consultado_em: str
    cnpj_mascarado: str
    razao_social: str | None = None
    nome_fantasia: str | None = None
    situacao_cadastral: str | None = None
    data_abertura: str | None = None
    idade_empresa_meses: int | None = None
    cnae_principal: CnaeNormalizado | None = None
    cnaes_secundarios: tuple[CnaeNormalizado, ...] = ()
    porte: str | None = None
    natureza_juridica: str | None = None
    matriz_filial: str | None = None
    capital_social: str | None = None
    situacao_especial: str | None = None
    campos_indisponiveis: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetricaBureau:
    disponivel: bool
    valor: Any = None
    quantidade: int | None = None
    valor_total: str | None = None
    faixa: str | None = None
    modelo: str | None = None
    encontrada: bool | None = None
    categorias: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ResultadoBureauNormalizado:
    """DTO interno de birô — campos não contratados usam disponivel=False, não zero."""

    provider: str
    produto: str
    consultado_em: str
    valido_ate: str | None
    cnpj_mascarado: str
    score: MetricaBureau
    dividas: MetricaBureau
    protestos: MetricaBureau
    acoes_judiciais: MetricaBureau
    falencia_recuperacao: MetricaBureau
    cheques_devolvidos: MetricaBureau
    capacidade_pagamento: MetricaBureau
    limite_sugerido_provider: MetricaBureau
    alertas: tuple[str, ...] = ()
    campos_nao_contratados: tuple[str, ...] = ()


@runtime_checkable
class ConsultaCadastralCNPJProvider(Protocol):
    def nome_provider(self) -> str: ...

    def versao_contrato(self) -> str: ...

    def validar_configuracao(self) -> bool: ...

    def capability(self) -> ProviderCapability: ...

    def consultar(self, cnpj: str, contexto: ContextoConsulta) -> ResultadoCadastralNormalizado: ...


@runtime_checkable
class CreditBureauProvider(Protocol):
    def nome_provider(self) -> str: ...

    def versao_produto(self) -> str: ...

    def validar_configuracao(self) -> bool: ...

    def capability(self) -> ProviderCapability: ...

    def consultar_empresa(
        self,
        cnpj: str,
        finalidade: str,
        id_solicitacao: str,
        contexto: ContextoConsulta,
    ) -> ResultadoBureauNormalizado: ...


# Tipos de evento futuros (não gerados nesta fundação)
EVENTO_CONSULTA_CADASTRAL_SOLICITADA = 'CONSULTA_CADASTRAL_SOLICITADA'
EVENTO_CONSULTA_CADASTRAL_CONCLUIDA = 'CONSULTA_CADASTRAL_CONCLUIDA'
EVENTO_CONSULTA_CADASTRAL_ERRO = 'CONSULTA_CADASTRAL_ERRO'
EVENTO_CONSULTA_BURO_SOLICITADA = 'CONSULTA_BURO_SOLICITADA'
EVENTO_CONSULTA_BURO_CONCLUIDA = 'CONSULTA_BURO_CONCLUIDA'
EVENTO_CONSULTA_BURO_ERRO = 'CONSULTA_BURO_ERRO'
EVENTO_CONSULTA_EXPIRADA = 'CONSULTA_EXPIRADA'
