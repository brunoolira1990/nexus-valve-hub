"""Sanitização de CNPJ, erros e payloads — fundação B2/B3."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)
_TOKENISH_RE = re.compile(
    r'(?i)(api[_-]?key|token|secret|authorization|bearer)\s*[:=]\s*\S+'
)
_CNPJ_DIGITS_RE = re.compile(r'\d{14}')


def normalizar_cnpj_digitos(cnpj: str | None) -> str:
    return ''.join(ch for ch in str(cnpj or '') if ch.isdigit())


def mascarar_cnpj(cnpj: str | None) -> str:
    """Retorna máscara estável sem expor o CNPJ completo (mantém 2 últimos dígitos)."""
    digits = normalizar_cnpj_digitos(cnpj)
    if len(digits) != 14:
        return '**.***.***/****-**'
    return f'**.***.***/****-{digits[-2:]}'


def limitar_texto(valor: str | None, *, max_len: int = 240) -> str:
    texto = str(valor or '').strip()
    if len(texto) <= max_len:
        return texto
    return texto[: max_len - 1] + '…'


def sanitizar_mensagem_erro(mensagem: str | None, *, fallback: str = 'Falha na integração externa.') -> str:
    texto = limitar_texto(mensagem, max_len=240)
    if not texto:
        return fallback
    texto = _URL_RE.sub('[url removida]', texto)
    texto = _TOKENISH_RE.sub(r'\1=[redacted]', texto)
    texto = _CNPJ_DIGITS_RE.sub(mascarar_cnpj, texto)
    return texto


def hash_requisicao(
    *,
    analise_id: int,
    cnpj: str,
    tipo: str,
    provider: str,
    produto: str,
    finalidade: str = '',
) -> str:
    cnpj_n = normalizar_cnpj_digitos(cnpj)
    raw = '|'.join(
        [
            str(analise_id),
            cnpj_n,
            (tipo or '').upper(),
            (provider or '').strip().lower(),
            (produto or '').strip().lower(),
            (finalidade or '').strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


CAMPOS_PROIBIDOS_RESULTADO = frozenset(
    {
        'raw',
        'payload',
        'response',
        'request',
        'headers',
        'token',
        'api_key',
        'secret',
        'authorization',
        'qsa',
        'socios',
        'pdf',
        'xml',
        'stack',
        'traceback',
    }
)


def validar_resultado_normalizado(payload: Any) -> dict[str, Any]:
    """Aceita apenas dict raso sanitizado; rejeita chaves proibidas."""
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError('resultado_normalizado deve ser um objeto JSON.')
    limpo: dict[str, Any] = {}
    for chave, valor in payload.items():
        k = str(chave).strip().lower()
        if k in CAMPOS_PROIBIDOS_RESULTADO:
            continue
        if isinstance(valor, (str, int, float, bool)) or valor is None:
            if isinstance(valor, str):
                limpo[chave] = limitar_texto(valor, max_len=500)
            else:
                limpo[chave] = valor
        elif isinstance(valor, (list, dict)):
            # Estruturas aninhadas permitidas sem raw; limpeza superficial de chaves.
            limpo[chave] = valor
    return limpo
