"""Consulta cadastral básica por CNPJ — somente leitura para formulários de cadastro.

Inscrição Estadual (IE) não faz parte desta consulta. A integração de IE será
feita em serviço separado (Sintegra/CCC), ainda a definir — ver consulta_ie.py.
"""

from __future__ import annotations

from typing import Any

from apps.cadastros.consulta_externa import _get_json, format_cep_br
from apps.cadastros.utils import normalizar_cnpj, validar_cnpj

AVISO_IE_FONTE_ATUAL = (
    'A fonte atual não retorna Inscrição Estadual para este CNPJ/UF.'
)


def normalizar_cnpj_digitos(cnpj: str | None) -> str:
    return ''.join(ch for ch in str(cnpj or '') if ch.isdigit())


def _parse_receitaws(payload: dict[str, Any]) -> dict[str, Any]:
    cep_raw = normalizar_cnpj_digitos(str(payload.get('cep') or ''))
    cep_fmt = format_cep_br(cep_raw) if len(cep_raw) == 8 else str(payload.get('cep') or '').strip()
    atividade = payload.get('atividade_principal')
    if isinstance(atividade, list) and atividade:
        atividade = atividade[0]
    if not isinstance(atividade, dict):
        atividade = {}
    cnae = str(atividade.get('code') or atividade.get('codigo') or '').strip()
    simples = str(payload.get('simples') or '').strip().lower()
    regime = 'Simples Nacional' if simples in {'sim', 'true', '1'} else ''
    uf = str(payload.get('uf') or '').strip().upper()[:2]

    return {
        'cnpj': str(payload.get('cnpj') or '').strip(),
        'razao_social': str(payload.get('nome') or '').strip(),
        'nome_fantasia': str(payload.get('fantasia') or '').strip(),
        'inscricao_estadual': '',
        'inscricao_estadual_disponivel': False,
        'cep': cep_fmt,
        'logradouro': str(payload.get('logradouro') or '').strip(),
        'numero': str(payload.get('numero') or '').strip(),
        'complemento': str(payload.get('complemento') or '').strip(),
        'bairro': str(payload.get('bairro') or '').strip(),
        'cidade': str(payload.get('municipio') or '').strip(),
        'uf': uf,
        'codigo_municipio': '',
        'cnae': cnae,
        'regime_tributario': regime,
        'telefone': str(payload.get('telefone') or '').strip(),
        'email': str(payload.get('email') or '').strip(),
        'fonte': 'receitaws',
        'aviso_ie': AVISO_IE_FONTE_ATUAL,
        'consulta_ie_pendente': True,
    }


def consultar_cnpj_cadastral(cnpj: str | None) -> tuple[dict[str, Any] | None, str]:
    """
    Consulta dados cadastrais básicos por CNPJ (ReceitaWS).
    Não retorna Inscrição Estadual — use futuro serviço dedicado de IE.
  """
    cnpj_canonico = normalizar_cnpj(cnpj)
    if len(cnpj_canonico) != 14:
        return None, 'CNPJ inválido. Informe 14 caracteres alfanuméricos.'
    if not validar_cnpj(cnpj_canonico):
        return None, 'CNPJ inválido. Verifique os dígitos verificadores.'
    if not cnpj_canonico.isdigit():
        return None, (
            'A consulta cadastral externa atual aceita apenas CNPJ numérico. '
            'Para CNPJ alfanumérico, informe os dados cadastrais manualmente.'
        )

    try:
        payload_rw = _get_json(f'https://receitaws.com.br/v1/cnpj/{cnpj_canonico}', timeout=10.0)
    except Exception:
        return None, 'Não foi possível consultar o CNPJ agora. Você pode preencher os dados manualmente.'

    status_receita = str(payload_rw.get('status') or '').lower()
    if status_receita == 'error':
        mensagem = str(payload_rw.get('message') or 'CNPJ não encontrado.').strip()
        return None, mensagem

    return _parse_receitaws(payload_rw), ''
