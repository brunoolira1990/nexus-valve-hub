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
