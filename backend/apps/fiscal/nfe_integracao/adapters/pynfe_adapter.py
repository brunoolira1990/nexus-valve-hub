"""Adaptador PyNFe — comunicação SEFAZ (sem SOAP manual)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.nfe_integracao.adapters.exceptions import PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.status_servico_parser import (
    log_diagnostico_resposta,
    normalizar_xml_bruto,
)


def criar_comunicacao_sefaz(
    uf: str,
    caminho_certificado: str,
    senha: str,
    *,
    homologacao: bool = True,
) -> Any:
    """Instancia ComunicacaoSefaz do PyNFe."""
    try:
        from pynfe.processamento.comunicacao import ComunicacaoSefaz
    except ImportError as exc:
        raise PyNFeComunicacaoError(
            f'PyNFe indisponível ({exc}). Instale PyNFe, signxml, requests e suds-py3 '
            '(requirements.txt) e reconstrua o container: docker compose build backend.',
        ) from exc

    uf_norm = (uf or 'SP').strip().lower()
    try:
        return ComunicacaoSefaz(uf_norm, caminho_certificado, senha, homologacao=homologacao)
    except Exception as exc:
        msg = str(exc).lower()
        if 'password' in msg or 'senha' in msg or 'mac verify' in msg or 'pkcs12' in msg:
            raise PyNFeComunicacaoError(
                'Certificado digital inválido ou senha incorreta.',
            ) from exc
        raise PyNFeComunicacaoError(f'Falha ao inicializar ComunicacaoSefaz: {exc}') from exc


def status_servico_nfe(
    comunicacao: Any,
    *,
    modelo: str = 'nfe',
    timeout: int | None = 30,
) -> Any:
    """
    Consulta status do serviço NF-e (NFeStatusServico4).

    Retorna objeto Response-like do requests com .text / .content.
    """
    try:
        return comunicacao.status_servico(modelo, timeout=timeout)
    except Exception as exc:
        msg = str(exc).lower()
        if 'timeout' in msg or 'timed out' in msg:
            raise PyNFeComunicacaoError(
                'WebService indisponível ou timeout ao consultar a SEFAZ.',
            ) from exc
        if 'connection' in msg or 'conex' in msg or 'network' in msg:
            raise PyNFeComunicacaoError(
                'Erro ao conectar ao WebService da SEFAZ.',
            ) from exc
        raise PyNFeComunicacaoError(f'Erro na consulta status_servico: {exc}') from exc


def extrair_xml_resposta(resposta: Any) -> str:
    """Normaliza corpo XML da resposta PyNFe (delega ao parser 3.6.1)."""
    log_diagnostico_resposta(resposta, contexto='extrair_xml_resposta')
    return normalizar_xml_bruto(resposta)
