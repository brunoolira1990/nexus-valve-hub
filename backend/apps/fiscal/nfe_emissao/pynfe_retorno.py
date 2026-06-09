"""Normalização do retorno de ComunicacaoSefaz.autorizacao (PyNFe)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetornoAutorizacaoPyNFe:
    """
    PyNFe retorna 2 ou 3 elementos:
    - sucesso síncrono: (0, nfeProc_element)
    - sucesso assíncrono: (0, nRec, nota_fiscal)
    - erro / rejeição: (1, response_ou_xml, nota_fiscal_opcional)
    """

    codigo: int
    resultado: Any
    nota_enviada: Any | None = None


def desempacotar_retorno_autorizacao_pynfe(retorno: Any) -> RetornoAutorizacaoPyNFe:
    if not isinstance(retorno, tuple):
        raise ValueError(f'Retorno PyNFe inválido (esperado tuple): {type(retorno).__name__}')
    if len(retorno) < 2:
        raise ValueError(f'Retorno PyNFe incompleto: {len(retorno)} valor(es)')
    codigo = int(retorno[0])
    resultado = retorno[1]
    nota_enviada = retorno[2] if len(retorno) > 2 else None
    return RetornoAutorizacaoPyNFe(codigo=codigo, resultado=resultado, nota_enviada=nota_enviada)
