"""Consultas externas CEP/CNPJ reutilizáveis pelo cadastro e validação fiscal."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _get_json(url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    req = Request(url, headers={'User-Agent': 'NexusERP/4.0'})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read().decode('utf-8')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError('Resposta inválida do serviço externo.') from exc


def format_cep_br(digits: str) -> str:
    if len(digits) != 8 or not digits.isdigit():
        return digits
    return f'{digits[:5]}-{digits[5:]}'


def normalizar_cep_digitos(cep: str | None) -> str:
    return ''.join(ch for ch in str(cep or '') if ch.isdigit())


def consultar_cep_viacep(cep: str | None, *, timeout: float = 8.0) -> dict[str, str] | None:
    """Consulta ViaCEP. Retorna dict normalizado ou None se CEP inválido/não encontrado."""
    cep_digitos = normalizar_cep_digitos(cep)
    if len(cep_digitos) != 8:
        return None
    try:
        payload = _get_json(f'https://viacep.com.br/ws/{cep_digitos}/json/', timeout=timeout)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None
    if payload.get('erro'):
        return None
    cep_fmt = (payload.get('cep') or '').strip() or format_cep_br(cep_digitos)
    return {
        'logradouro': payload.get('logradouro', '') or '',
        'complemento': payload.get('complemento', '') or '',
        'bairro': payload.get('bairro', '') or '',
        'cidade': payload.get('localidade', '') or '',
        'uf': (payload.get('uf', '') or '').upper()[:2],
        'cep': cep_fmt,
    }
