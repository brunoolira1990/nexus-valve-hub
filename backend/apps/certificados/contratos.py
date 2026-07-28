"""Contratos e DTOs seguros da fachada A1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class FinalidadeCertificado(str, Enum):
    FISCAL_SEFAZ = 'FISCAL_SEFAZ'
    CONSULTA_CENPROT = 'CONSULTA_CENPROT'


@dataclass(frozen=True)
class MetadadosCertificadoSeguros:
    """Metadados não sensíveis — nunca incluem senha, PEM, path, subject ou serial."""

    disponivel: bool
    valido: bool
    tipo: str
    finalidade: str
    vence_em: date | None
    dias_para_expirar: int | None
    motivo_indisponibilidade: str | None = None


@dataclass
class MaterialCriptograficoA1:
    """
    Contexto efêmero em memória.

    Não serializar, não colocar em cache global, não persistir PEM.
    """

    certificado: Any
    chave_privada: Any
    cadeia: tuple[Any, ...]
    finalidade: FinalidadeCertificado
    carregado_em: datetime
    _liberado: bool = False

    def liberar(self) -> None:
        self.certificado = None
        self.chave_privada = None
        self.cadeia = ()
        self._liberado = True
