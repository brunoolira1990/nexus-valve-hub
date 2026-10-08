"""Respostas padronizadas — validação e preview XML NF-e entrada própria."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeEntrada


def montar_resposta_validacao_entrada(validacao: dict[str, Any], *, nf: NFeEntrada | None = None) -> dict[str, Any]:
    payload = {
        'ok': bool(validacao.get('pronta')),
        'pronta': bool(validacao.get('pronta')),
        'pendencias': list(validacao.get('pendencias') or []),
        'alertas': list(validacao.get('alertas') or []),
        'mensagem': validacao.get('mensagem') or '',
        'ambiente': validacao.get('ambiente') or 'homologacao',
        'sem_transmissao': True,
        'sem_assinatura': True,
    }
    if nf:
        payload['nf_entrada_id'] = nf.pk
        payload['tipo_origem'] = nf.tipo_origem
        payload['status_operacional'] = nf.status_operacional
        payload['status_emissao_sefaz'] = nf.status_emissao_sefaz or ''
    elif validacao.get('nf_entrada_id'):
        payload['nf_entrada_id'] = validacao['nf_entrada_id']
    return payload
