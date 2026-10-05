"""Reconstrução de <nfeProc> para NF-e de entrada própria autorizada.

Quando a resposta SEFAZ se perde (timeout/crash), xml_autorizado fica vazio.
Se xml_assinado + protocolo_autorizacao + dados da consulta existem, é possível
remontar o <nfeProc> localmente. É o mesmo XML que a SEFAZ devolveria — o DANFE
gerado a partir dele tem validade fiscal idêntica.
"""

from __future__ import annotations

import re
from typing import Any

from apps.fiscal.models import NFeEntrada

VERSAO_NFE = '4.00'


class NFeEntradaXmlAutorizadoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'VALIDACAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def _extrair_nfe_do_xml_assinado(xml_assinado: str) -> str:
    """Extrai o bloco <NFe>...</NFe> do XML assinado, removendo declaração/wrappers."""
    if not xml_assinado:
        raise NFeEntradaXmlAutorizadoError('NF-e sem XML assinado em memória.')

    m = re.search(r'<NFe\b[^>]*>.*?</NFe>', xml_assinado, re.DOTALL)
    if not m:
        raise NFeEntradaXmlAutorizadoError(
            'XML assinado não contém elemento <NFe>. Reconstrução impossível.'
        )
    return m.group(0)


def _tp_amb(nf: NFeEntrada) -> str:
    return '1' if (nf.ambiente_emissao or '').lower() == 'producao' else '2'


def reconstruir_xml_autorizado_entrada(
    nf: NFeEntrada,
    *,
    dh_recbto: str | None = None,
    ver_aplic: str = 'SP_NFE_PL009_V4',
) -> str:
    """Monta o <nfeProc> e retorna a string. Não persiste — caller decide salvar."""
    chave = (nf.chave_acesso or '').strip()
    if len(chave) != 44:
        raise NFeEntradaXmlAutorizadoError('NF-e sem chave de acesso válida (44 dígitos).')

    protocolo = (nf.protocolo_autorizacao or '').strip()
    if not protocolo:
        raise NFeEntradaXmlAutorizadoError('NF-e sem protocolo de autorização.')

    cstat = (nf.cstat_autorizacao or '').strip()
    if cstat != '100':
        raise NFeEntradaXmlAutorizadoError(
            f'cStat atual é {cstat!r}, esperado 100 (Autorizado).',
            etapa='STATUS',
        )

    motivo = (nf.motivo_autorizacao or '').strip() or 'Autorizado o uso da NF-e'
    nfe_inner = _extrair_nfe_do_xml_assinado(nf.xml_assinado or '')
    ambiente = _tp_amb(nf)
    dh = (dh_recbto or '').strip() or ''

    prot = (
        f'<protNFe versao="{VERSAO_NFE}">'
        f'<infProt Id="ID{protocolo}">'
        f'<tpAmb>{ambiente}</tpAmb>'
        f'<verAplic>{ver_aplic}</verAplic>'
        f'<chNFe>{chave}</chNFe>'
        + (f'<dhRecbto>{dh}</dhRecbto>' if dh else '')
        + f'<nProt>{protocolo}</nProt>'
        f'<cStat>{cstat}</cStat>'
        f'<xMotivo>{motivo}</xMotivo>'
        f'</infProt>'
        f'</protNFe>'
    )

    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="{VERSAO_NFE}">'
        f'{nfe_inner}'
        f'{prot}'
        f'</nfeProc>'
    )


def aplicar_reconstrucao_xml_autorizado(
    nf: NFeEntrada,
    *,
    dh_recbto: str | None = None,
) -> dict[str, Any]:
    """Gera <nfeProc> e salva em nf.xml_autorizado. Idempotente se já existir conteúdo."""
    if (nf.xml_autorizado or '').strip():
        return {
            'ok': True,
            'ja_existia': True,
            'mensagem': 'XML autorizado já estava preenchido.',
            'tamanho': len(nf.xml_autorizado),
        }

    xml = reconstruir_xml_autorizado_entrada(nf, dh_recbto=dh_recbto)
    nf.xml_autorizado = xml
    nf.save(update_fields=['xml_autorizado'])

    return {
        'ok': True,
        'ja_existia': False,
        'mensagem': 'XML autorizado reconstruído a partir do XML assinado + protocolo.',
        'tamanho': len(xml),
    }
