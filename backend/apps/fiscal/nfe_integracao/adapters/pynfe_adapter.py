"""Adaptador PyNFe — comunicação SEFAZ (sem SOAP manual)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from apps.fiscal.nfe_integracao.adapters.exceptions import PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.status_servico_parser import (
    log_diagnostico_resposta,
    normalizar_xml_bruto,
)

logger = logging.getLogger(__name__)


_PROXY_ENV_KEYS = (
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'http_proxy',
    'https_proxy',
    'ALL_PROXY',
    'all_proxy',
)


@contextmanager
def requests_sem_proxy_ambiente() -> Iterator[None]:
    """
    Evita que HTTP(S)_PROXY do host (WSL/Docker/corporativo) desvie chamadas SEFAZ
    para páginas HTML de proxy/captive portal em dev/local.
    """
    import os

    import requests

    proxy_backup = {key: os.environ.pop(key, None) for key in _PROXY_ENV_KEYS}
    original_post = requests.post
    original_session_request = requests.Session.request
    original_session_init = requests.Session.__init__

    def post_sem_proxy(*args: Any, **kwargs: Any) -> Any:
        proxies = dict(kwargs.get('proxies') or {})
        proxies.setdefault('http', None)
        proxies.setdefault('https', None)
        kwargs['proxies'] = proxies
        return original_post(*args, **kwargs)

    def session_request_sem_proxy(self: Any, method: str, url: str, **kwargs: Any) -> Any:
        proxies = dict(kwargs.get('proxies') or {})
        proxies.setdefault('http', None)
        proxies.setdefault('https', None)
        kwargs['proxies'] = proxies
        return original_session_request(self, method, url, **kwargs)

    def session_init_sem_proxy(self: Any, *args: Any, **kwargs: Any) -> None:
        original_session_init(self, *args, **kwargs)
        self.trust_env = False

    requests.post = post_sem_proxy  # type: ignore[method-assign]
    requests.Session.request = session_request_sem_proxy  # type: ignore[method-assign]
    requests.Session.__init__ = session_init_sem_proxy  # type: ignore[method-assign]
    try:
        yield
    finally:
        requests.post = original_post  # type: ignore[method-assign]
        requests.Session.request = original_session_request  # type: ignore[method-assign]
        requests.Session.__init__ = original_session_init  # type: ignore[method-assign]
        for key, value in proxy_backup.items():
            if value is not None:
                os.environ[key] = value


def resolver_url_status_servico(comunicacao: Any, *, modelo: str = 'nfe') -> str:
    """Resolve URL pública do webservice NFeStatusServico4 (sem dados sensíveis)."""
    try:
        return str(comunicacao._get_url(modelo, 'STATUS') or '')
    except Exception as exc:
        logger.debug('Falha ao resolver URL status_servico: %s', exc)
        return ''


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
        with requests_sem_proxy_ambiente():
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


def consulta_cadastro_contribuinte(
    comunicacao: Any,
    documento: str,
    *,
    uf: str,
    tipo: str = 'CNPJ',
    modelo: str = 'nfe',
) -> Any:
    """Consulta cadastro do contribuinte (NFeConsultaCadastro / CadConsultaCadastro4)."""
    doc = ''.join(ch for ch in str(documento or '') if ch.isdigit())
    uf_norm = (uf or '').strip().upper()
    if len(doc) not in {11, 14}:
        raise PyNFeComunicacaoError('CNPJ inválido para consulta cadastral SEFAZ.')
    if len(uf_norm) != 2:
        raise PyNFeComunicacaoError('UF inválida para consulta cadastral SEFAZ.')
    try:
        with requests_sem_proxy_ambiente():
            return comunicacao.consulta_cadastro(modelo, doc, tipo=tipo.upper(), uf=uf_norm)
    except PyNFeComunicacaoError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if 'timeout' in msg or 'timed out' in msg:
            raise PyNFeComunicacaoError(
                'Tempo esgotado ao consultar cadastro na SEFAZ. Tente novamente em instantes.',
            ) from exc
        if 'connection' in msg or 'conex' in msg or 'network' in msg:
            raise PyNFeComunicacaoError('Erro ao conectar ao WebService da SEFAZ.') from exc
        if 'cadastro' in msg and ('url' in msg or 'endpoint' in msg or 'not found' in msg):
            raise PyNFeComunicacaoError(
                'Consulta cadastral SEFAZ não configurada para esta UF.',
            ) from exc
        raise PyNFeComunicacaoError(f'Erro na consulta cadastro SEFAZ: {exc}') from exc


def consulta_situacao_nfe(
    comunicacao: Any,
    chave_acesso: str,
    *,
    modelo: str = 'nfe',
) -> Any:
    """Consulta situação da NF-e na SEFAZ (NFeConsultaProtocolo4 / consSitNFe)."""
    chave = (chave_acesso or '').strip()
    if len(chave) != 44 or not chave.isdigit():
        raise PyNFeComunicacaoError('Chave de acesso inválida para consulta SEFAZ.')
    try:
        with requests_sem_proxy_ambiente():
            return comunicacao.consulta_nota(modelo, chave)
    except PyNFeComunicacaoError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if 'timeout' in msg or 'timed out' in msg:
            raise PyNFeComunicacaoError(
                'Tempo esgotado ao consultar a SEFAZ. Verifique certificado/rede e tente novamente.',
            ) from exc
        if 'connection' in msg or 'conex' in msg or 'network' in msg:
            raise PyNFeComunicacaoError('Erro ao conectar ao WebService da SEFAZ.') from exc
        raise PyNFeComunicacaoError(f'Erro na consulta situação NF-e: {exc}') from exc


def transmitir_evento_nfe(
    comunicacao: Any,
    evento_assinado: Any,
    *,
    modelo: str = 'nfe',
    id_lote: int = 1,
) -> Any:
    """Transmite evento NF-e à SEFAZ (NFeRecepcaoEvento4 — CC-e, cancelamento, etc.)."""
    try:
        with requests_sem_proxy_ambiente():
            return comunicacao.evento(modelo, evento_assinado, id_lote=id_lote)
    except PyNFeComunicacaoError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if 'timeout' in msg or 'timed out' in msg:
            raise PyNFeComunicacaoError(
                'Tempo esgotado ao transmitir evento à SEFAZ. Verifique certificado/rede e tente novamente.',
            ) from exc
        if 'connection' in msg or 'conex' in msg or 'network' in msg:
            raise PyNFeComunicacaoError('Erro ao conectar ao WebService da SEFAZ.') from exc
        raise PyNFeComunicacaoError(f'Erro na transmissão do evento NF-e: {exc}') from exc
