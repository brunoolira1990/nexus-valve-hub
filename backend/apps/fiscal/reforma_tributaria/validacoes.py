"""Validações e alertas — Reforma Tributária NF-e."""

from __future__ import annotations

from apps.fiscal.models import NFeSaida
from apps.fiscal.reforma_tributaria.config import reforma_nfe_config


MSG_REFORMA_NAO_PREPARADA = (
    'Reforma Tributária ainda não preparada para geração de XML/DANFE. '
    'Conclua a configuração antes de novo teste de homologação.'
)


def reforma_pode_incluir_no_xml() -> bool:
    """Flag de homologação RTC ativa (controle operacional, sem exigir ``incluir_xml``)."""
    cfg = reforma_nfe_config()
    if cfg['modo'] == 'producao' and cfg.get('producao_bloqueada'):
        return False
    return cfg['enabled'] and cfg['modo'] in ('homologacao', 'preparacao', 'producao')


def reforma_deve_serializar_no_xml() -> bool:
    """True quando grupos IBSCBS/IBSCBSTot devem entrar no XML oficial de emissão."""
    cfg = reforma_nfe_config()
    return reforma_pode_incluir_no_xml() and bool(cfg['incluir_xml'])


def reforma_pode_incluir_no_danfe() -> bool:
    cfg = reforma_nfe_config()
    return (
        cfg['enabled']
        and cfg['incluir_danfe']
        and cfg['modo'] == 'homologacao'
        and reforma_pode_incluir_no_xml()
    )


def alerta_reforma_antes_homologacao(nf: NFeSaida | None = None) -> str | None:
    """
    Alerta quando modo homologacao+XML está ativo mas builders ainda não implementados.
    Com flags padrão (pesquisa), retorna None — emissão atual não é bloqueada.
    """
    _ = nf
    cfg = reforma_nfe_config()
    if not cfg['enabled']:
        return None
    if cfg['modo'] in ('pesquisa', 'preparacao'):
        return None
    if cfg['modo'] == 'producao':
        return 'Geração da Reforma Tributária em produção bloqueada nesta fase.'
    return None
