"""Configuração e feature flags — Reforma Tributária NF-e."""

from __future__ import annotations

from typing import Any, Literal

from django.conf import settings

ModoReformaNfe = Literal['pesquisa', 'preparacao', 'homologacao', 'producao']

MODOS_VALIDOS = frozenset({'pesquisa', 'preparacao', 'homologacao', 'producao'})


def reforma_nfe_config() -> dict[str, Any]:
    modo = (getattr(settings, 'REFORMA_TRIBUTARIA_NFE_MODO', 'pesquisa') or 'pesquisa').strip().lower()
    if modo not in MODOS_VALIDOS:
        modo = 'pesquisa'
    return {
        'enabled': bool(getattr(settings, 'REFORMA_TRIBUTARIA_NFE_ENABLED', False)),
        'modo': modo,
        'ambiente_homologacao': bool(getattr(settings, 'REFORMA_TRIBUTARIA_NFE_AMBIENTE_HOMOLOGACAO', True)),
        'incluir_xml': bool(getattr(settings, 'REFORMA_TRIBUTARIA_NFE_INCLUIR_XML', False)),
        'incluir_danfe': bool(getattr(settings, 'REFORMA_TRIBUTARIA_NFE_INCLUIR_DANFE', False)),
        'producao_bloqueada': True,
    }


def status_reforma_nfe_documento(nf) -> str:
    """
    Retorno para API/UI:
    nao_aplicavel | nao_preparada | preparacao | homologacao | bloqueada_producao | configurada_sem_xml
    """
    cfg = reforma_nfe_config()
    if not cfg['enabled']:
        return 'nao_aplicavel'
    if cfg['modo'] == 'pesquisa':
        return 'nao_preparada'
    if cfg['modo'] == 'preparacao':
        if _nf_tem_reforma_configurada(nf):
            return 'preparacao'
        return 'nao_preparada'
    if cfg['modo'] == 'homologacao':
        if cfg['incluir_xml'] or cfg['incluir_danfe']:
            return 'homologacao'
        if _nf_tem_reforma_configurada(nf):
            return 'configurada_sem_xml'
        return 'preparacao'
    if cfg['modo'] == 'producao':
        return 'bloqueada_producao'
    return 'nao_preparada'


def _nf_tem_reforma_configurada(nf) -> bool:
    from apps.fiscal.snapshot_fiscal_helpers import reforma_configurada_no_snapshot

    if not hasattr(nf, 'itens'):
        return False
    for item in nf.itens.all():
        if reforma_configurada_no_snapshot(item.snapshot_fiscal):
            return True
    return False
