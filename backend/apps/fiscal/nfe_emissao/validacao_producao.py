"""Validação pré-emissão NF-e Saída produção SEFAZ — separada da homologação."""

from __future__ import annotations

import re
from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.config_producao import MSG_PRODUCAO_NAO_HABILITADA, nfe_producao_habilitada
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao
from apps.fiscal.nfe_emissao.validacao import (
    MSG_CERTIFICADO_A1,
    NFeEmissaoValidacaoError,
    _validar_empresa_emitente,
)
from apps.fiscal.nfe_emissao.validacao_util import extrair_mensagens_pendencias_validacao
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error
from apps.fiscal.reforma_tributaria.config import reforma_nfe_config, status_reforma_nfe_documento
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao


def _pendencia(codigo: str, mensagem: str, *, severidade: str = 'bloqueio') -> dict[str, str]:
    return {'codigo': codigo, 'mensagem': mensagem, 'severidade': severidade}


def montar_validacao_emissao_producao(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Checklist read-only — pronta / pendências / alertas (sem transmitir)."""
    pendencias: list[dict[str, str]] = []
    alertas: list[dict[str, str]] = []

    if not nfe_producao_habilitada():
        pendencias.append(_pendencia('producao_desabilitada', MSG_PRODUCAO_NAO_HABILITADA))

    if nfe_saida.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
        pendencias.append(_pendencia('ja_autorizada_producao', 'NF-e já autorizada em produção SEFAZ.'))

    if nfe_saida.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        pendencias.append(
            _pendencia(
                'ja_autorizada_homolog',
                'NF-e já autorizada em homologação — use nova NF-e para produção.',
            ),
        )

    if (
        nfe_saida.ambiente_emissao == NFeSaida.AmbienteEmissao.HOMOLOGACAO
        and (nfe_saida.chave_acesso or '').strip()
    ):
        pendencias.append(
            _pendencia(
                'numeracao_homolog_reservada',
                'Numeração de homologação já reservada — use nova NF-e para produção.',
            ),
        )

    conf = (nfe_saida.status_conferencia or '').strip()
    if conf != NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO:
        pendencias.append(
            _pendencia(
                'conferencia_nao_pronta',
                'NF-e deve estar com status «Pronta para emissão» na conferência.',
            ),
        )

    val = validar_nfe_saida_para_emissao(nfe_saida)
    for msg in extrair_mensagens_pendencias_validacao(val):
        pendencias.append(_pendencia('validacao_fiscal', msg))

    cfg_rtc = reforma_nfe_config()
    rtc_status = status_reforma_nfe_documento(nfe_saida)
    if cfg_rtc['modo'] == 'producao' and cfg_rtc.get('producao_bloqueada'):
        pendencias.append(
            _pendencia(
                'reforma_producao_bloqueada',
                'Geração em produção bloqueada até validação oficial da Reforma Tributária.',
            ),
        )
    elif rtc_status == 'bloqueada_producao':
        alertas.append(
            _pendencia(
                'reforma_status',
                f'Status Reforma Tributária: {rtc_status}.',
                severidade='alerta',
            ),
        )

    try:
        empresa = resolver_empresa_emitente_nfe(nfe_saida)
        from apps.cadastros.nfe_ambiente import empresa_configurada_para_producao

        if not empresa_configurada_para_producao(empresa):
            pendencias.append(
                _pendencia(
                    'empresa_ambiente_homolog',
                    'Empresa configurada para Homologação. '
                    'Altere o ambiente NF-e no cadastro da empresa para Produção.',
                ),
            )
        for msg in _validar_empresa_emitente(empresa):
            pendencias.append(_pendencia('empresa_emitente', msg))
        try:
            cert = carregar_certificado_empresa(empresa)
            if not cert.valido:
                pendencias.append(_pendencia('certificado_a1', MSG_CERTIFICADO_A1))
        except CertificadoA1Error:
            pendencias.append(_pendencia('certificado_a1', MSG_CERTIFICADO_A1))

        obter_config_numeracao(empresa.pk, ambiente='producao')
    except NFeNumeracaoError as exc:
        pendencias.append(_pendencia('numeracao_producao', str(exc)))
    except Exception as exc:
        pendencias.append(_pendencia('empresa_emitente', str(exc)))

    if nfe_saida.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO and (nfe_saida.xml_assinado or '').strip():
        for msg in validar_xml_emissao_producao_local(nfe_saida.xml_assinado, nfe_saida=nfe_saida):
            pendencias.append(_pendencia('xml_producao', msg))

    from apps.fiscal.danfe_render import emissao_bloqueada_se_bfr_falhar

    if emissao_bloqueada_se_bfr_falhar():
        alertas.append(
            _pendencia(
                'danfe_bfr_obrigatorio',
                'DANFE oficial BFR obrigatório — falha no renderer bloqueia emissão.',
                severidade='alerta',
            ),
        )

    pronta = len(pendencias) == 0
    return {
        'pronta': pronta,
        'pendencias': pendencias,
        'alertas': alertas,
        'producao_habilitada': nfe_producao_habilitada(),
        'ambiente_emissao': nfe_saida.ambiente_emissao or '',
    }


def montar_validacao_preparacao_producao(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Checklist produção aplicável antes de marcar pronta (sem exigir status pronta)."""
    payload = montar_validacao_emissao_producao(nfe_saida)
    pendencias = [
        p for p in payload.get('pendencias', [])
        if p.get('codigo') != 'conferencia_nao_pronta'
    ]
    pronta = len(pendencias) == 0
    return {
        'pronta': pronta,
        'pendencias': pendencias,
        'alertas': payload.get('alertas') or [],
    }


def validar_pre_emissao_producao(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Validação bloqueante antes de reservar/transmitir produção."""
    from apps.fiscal.nfe_emissao.config_producao import exigir_producao_habilitada

    exigir_producao_habilitada()
    payload = montar_validacao_emissao_producao(nfe_saida)
    erros = [p['mensagem'] for p in payload['pendencias']]
    if erros:
        raise NFeEmissaoValidacaoError(erros)
    return {'ok': True, 'validacao': payload}


def validar_xml_emissao_producao_local(xml: str, *, nfe_saida: NFeSaida) -> list[str]:
    erros: list[str] = []
    if not xml.strip():
        erros.append('XML vazio.')
        return erros

    m_amb = re.search(r'<[\w:]*tpAmb>([12])</[\w:]*tpAmb>', xml)
    if not m_amb or m_amb.group(1) != '1':
        erros.append('tpAmb deve ser 1 (produção).')

    if nfe_saida.ambiente_emissao != NFeSaida.AmbienteEmissao.PRODUCAO:
        erros.append('NF-e não está configurada para ambiente de produção.')

    m_mod = re.search(r'<[\w:]*mod>(\d+)</[\w:]*mod>', xml)
    if not m_mod or m_mod.group(1) != '55':
        erros.append('XML deve ser modelo 55.')

    return erros
