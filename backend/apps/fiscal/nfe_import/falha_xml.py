"""
Formato padronizado de falhas na importação XML (NF-e / evento) para API e diagnóstico no cliente.
"""

from __future__ import annotations

import traceback
from typing import Any

TIPO_DOC_API = frozenset({'NFE', 'EVENTO', 'CANCELAMENTO', 'DESCONHECIDO'})


def normalizar_tipo_documento_api(
    raw: str | None,
    *,
    evento_cancelamento: bool = False,
) -> str:
    if evento_cancelamento:
        return 'CANCELAMENTO'
    r = (raw or '').strip().lower()
    if r == 'evento':
        return 'EVENTO'
    if r == 'nfe':
        return 'NFE'
    return 'DESCONHECIDO'


def montar_falha_importacao_xml(
    *,
    arquivo: str,
    chave: str = '',
    tipo_documento: str,
    tipo_erro: str,
    mensagem_completa: str,
    acao_sugerida: str,
    detalhe_tecnico: str | None = None,
) -> dict[str, Any]:
    """
    Retorna dict com campos estáveis para UI e cópia de diagnóstico.

    - erro: mensagem curta (mesma linha principal, truncada se muito longa)
    - detalhe: mensagem completa + opcional stack/exceção (não omitir)
    - mensagem: alias de detalhe (compatibilidade com clientes antigos)
    """
    doc = tipo_documento if tipo_documento in TIPO_DOC_API else 'DESCONHECIDO'
    base = (mensagem_completa or '').strip()
    tech = (detalhe_tecnico or '').strip()
    detalhe = base
    if tech:
        detalhe = f'{base}\n\n--- Detalhe técnico ---\n{tech}'
    erro_curto = base
    if len(erro_curto) > 200:
        erro_curto = erro_curto[:197] + '...'
    return {
        'arquivo': arquivo or 'sem_nome.xml',
        'chave': chave or '',
        'tipo_documento': doc,
        'tipo_erro': tipo_erro,
        'erro': erro_curto,
        'detalhe': detalhe,
        'acao_sugerida': (acao_sugerida or '').strip(),
        'mensagem': detalhe,
    }


def falha_com_traceback(
    *,
    arquivo: str,
    chave: str = '',
    tipo_documento: str,
    tipo_erro: str,
    mensagem_completa: str,
    acao_sugerida: str,
    exc: BaseException,
) -> dict[str, Any]:
    return montar_falha_importacao_xml(
        arquivo=arquivo,
        chave=chave,
        tipo_documento=tipo_documento,
        tipo_erro=tipo_erro,
        mensagem_completa=mensagem_completa,
        acao_sugerida=acao_sugerida,
        detalhe_tecnico=f'{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}',
    )
