"""Consulta situação NF-e na SEFAZ — read-only, sem emitir/cancelar/corrigir."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.resposta_consulta import montar_resposta_consulta_situacao
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.consulta_situacao_parser import (
    CSTAT_AUTORIZADO,
    CSTAT_CANCELADO,
    CSTAT_DENEGADO,
    ResultadoConsultaSituacaoSefaz,
    parse_consulta_situacao_resposta,
)
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    consulta_situacao_nfe,
    criar_comunicacao_sefaz,
    extrair_xml_resposta,
)
from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)

MSG_SEM_CHAVE = 'NF-e sem chave de acesso para consulta SEFAZ.'
MSG_STATUS_INCOMPATIVEL = (
    'Consulta SEFAZ disponível apenas para NF-e autorizada em homologação ou produção.'
)


class NFeConsultaSituacaoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'VALIDACAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def _chave_consulta(nf: NFeSaida) -> str:
    return (nf.chave_acesso or '').strip()


def pode_consultar_situacao_sefaz(nf: NFeSaida) -> tuple[bool, str]:
    chave = _chave_consulta(nf)
    if len(chave) != 44:
        return False, MSG_SEM_CHAVE

    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    st = (nf.status or '').strip().upper()
    autorizada_homolog = (
        sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        or st == 'AUTORIZADA_HOMOLOGACAO'
    )
    autorizada_producao = sefaz in (
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        'AUTORIZADA',
    ) or st in ('AUTORIZADA', 'EMITIDA', 'EMITIDO')
    if autorizada_homolog or autorizada_producao:
        return True, ''
    return False, MSG_STATUS_INCOMPATIVEL


def _homologacao_da_nfe(nf: NFeSaida) -> bool:
    amb = (nf.ambiente_emissao or '').strip().lower()
    if amb == NFeSaida.AmbienteEmissao.PRODUCAO:
        return False
    if amb == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
        return True
    return nf_autorizada_homologacao(nf) or (
        (nf.status_emissao_sefaz or '').strip() == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
    )


def _sincronizar_status_local_inequivoco(nf: NFeSaida, resultado: ResultadoConsultaSituacaoSefaz) -> bool:
    """Atualiza status local somente quando a SEFAZ indica situação inequívoca."""
    cstat = resultado.c_stat
    if not cstat:
        return False

    update_fields: list[str] = []
    status_anterior = nf.status_emissao_sefaz or ''
    homolog = _homologacao_da_nfe(nf)

    if cstat in CSTAT_AUTORIZADO:
        if resultado.protocolo and resultado.protocolo != (nf.protocolo_autorizacao or ''):
            nf.protocolo_autorizacao = resultado.protocolo
            update_fields.append('protocolo_autorizacao')
        if resultado.x_motivo and resultado.x_motivo != (nf.motivo_autorizacao or ''):
            nf.motivo_autorizacao = resultado.x_motivo
            update_fields.append('motivo_autorizacao')
        if cstat != (nf.cstat_autorizacao or ''):
            nf.cstat_autorizacao = cstat
            update_fields.append('cstat_autorizacao')
        alvo = (
            NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
            if homolog
            else NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
        )
        if status_anterior != alvo:
            nf.status_emissao_sefaz = alvo
            update_fields.append('status_emissao_sefaz')
    elif cstat in CSTAT_CANCELADO:
        nf.cstat_autorizacao = cstat
        nf.motivo_autorizacao = resultado.x_motivo or nf.motivo_autorizacao
        update_fields.extend(['cstat_autorizacao', 'motivo_autorizacao'])
        if (nf.status or '').strip().upper() not in ('CANCELADA', 'CANCELADA_INTERNA', 'CANCELADO'):
            nf.status = 'CANCELADA'
            update_fields.append('status')
    elif cstat in CSTAT_DENEGADO:
        if cstat != (nf.cstat_autorizacao or ''):
            nf.cstat_autorizacao = cstat
            update_fields.append('cstat_autorizacao')
        if resultado.x_motivo and resultado.x_motivo != (nf.motivo_autorizacao or ''):
            nf.motivo_autorizacao = resultado.x_motivo
            update_fields.append('motivo_autorizacao')

    if update_fields:
        nf.save(update_fields=list(dict.fromkeys(update_fields)))
        return True
    return False


@transaction.atomic
def consultar_situacao_nfe_saida(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    pode, motivo = pode_consultar_situacao_sefaz(nf)
    if not pode:
        raise NFeConsultaSituacaoError(motivo)

    chave = _chave_consulta(nf)
    empresa = resolver_empresa_emitente_nfe(nf)
    homolog = _homologacao_da_nfe(nf)
    ambiente_label = 'homologacao' if homolog else 'producao'

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeConsultaSituacaoError(str(exc), etapa='CERTIFICADO') from exc

    senha = (empresa.senha_certificado or '').strip()
    uf = (empresa.uf or 'SP').strip()

    logger.info(
        'CONSULTA_SITUACAO_SEFAZ_INICIO nfe_id=%s chave=%s ambiente=%s',
        nf.pk,
        chave,
        ambiente_label,
    )

    try:
        comunicacao = criar_comunicacao_sefaz(uf, cert.caminho, senha, homologacao=homolog)
        resposta_bruta = consulta_situacao_nfe(comunicacao, chave)
        xml_retorno = extrair_xml_resposta(resposta_bruta)
        resultado = parse_consulta_situacao_resposta(xml_retorno)
    except PyNFeComunicacaoError as exc:
        logger.warning('CONSULTA_SITUACAO_SEFAZ_ERRO nfe_id=%s msg=%s', nf.pk, exc)
        raise NFeConsultaSituacaoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc

    status_atualizado = _sincronizar_status_local_inequivoco(nf, resultado)
    nf.refresh_from_db()

    consultado_em = timezone.now()
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.CONSULTA_SITUACAO_SEFAZ,
        status_anterior=nf.status or '',
        status_novo=nf.status or '',
        resumo={
            'ambiente': ambiente_label,
            'chave_acesso': chave,
            'cStat': resultado.c_stat,
            'xMotivo': resultado.x_motivo,
            'protocolo': resultado.protocolo,
            'dh_recbto': resultado.dh_recbto,
            'consultado_em': consultado_em.isoformat(),
            'status_local_atualizado': status_atualizado,
            'autorizada': resultado.autorizada,
            'cancelada': resultado.cancelada,
            'denegada': resultado.denegada,
        },
        observacao='Consulta situação NF-e na SEFAZ (sem emitir, cancelar ou corrigir).',
        usuario=usuario,
    )

    logger.info(
        'CONSULTA_SITUACAO_SEFAZ_OK nfe_id=%s cStat=%s protocolo=%s status_atualizado=%s',
        nf.pk,
        resultado.c_stat,
        resultado.protocolo,
        status_atualizado,
    )

    return montar_resposta_consulta_situacao(
        nf,
        resultado,
        ok=resultado.ok,
        status_local_atualizado=status_atualizado,
    )
