"""Consulta situação NF-e na SEFAZ — read-only, sem emitir/cancelar/corrigir."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeEntrada, NFeNumeracaoConfiguracao, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.aplicar_resultado import _parse_dh_recbto
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
from apps.fiscal.nfe_saida_bloqueio import (
    nf_autorizada_homologacao,
    nf_cancelada_operacional,
    nf_tem_xml_autorizado_local,
)
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)

MSG_SEM_CHAVE = 'NF-e sem chave de acesso para consulta SEFAZ.'
MSG_STATUS_INCOMPATIVEL = (
    'Consulta SEFAZ disponível apenas para NF-e autorizada em homologação ou produção.'
)
MSG_SEFAZ_JA_REGISTROU = (
    'Rejeição 204 (duplicidade): a SEFAZ já registrou este documento — '
    'situação recuperada por consulta de situação.'
)

CSTAT_REJEICAO_DUPLICIDADE = '204'

_STATUS_TERMINAIS_SEM_SINCRONIZACAO = frozenset({
    NFeEntrada.StatusEmissaoSefaz.INUTILIZADA_HOMOLOGACAO,
    NFeEntrada.StatusEmissaoSefaz.INUTILIZADA_PRODUCAO,
})

# Estados em que a NF-e foi entregue à SEFAZ mas o ERP pode não ter gravado o protocolo.
_STATUS_TRANSMITIDOS_RECUPERAVEIS = frozenset({
    NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
    NFeSaida.StatusEmissaoSefaz.ENVIADA_PRODUCAO,
    NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
    NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO,
    NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO,
})


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


def _xml_contem_protocolo(xml: str | None, protocolo: str) -> bool:
    return bool(protocolo) and protocolo in (xml or '')


def _houve_tentativa_transmissao(nf: NFeSaida) -> bool:
    """True quando a NF-e chegou à SEFAZ — inclusive quando a resposta se perdeu em timeout."""
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    if sefaz in _STATUS_TRANSMITIDOS_RECUPERAVEIS:
        return True
    return bool((nf.cstat_lote or '').strip() or (nf.recibo_lote or '').strip() or (nf.xml_retorno or '').strip())


def pode_sincronizar_com_sefaz(nf: NFeSaida) -> tuple[bool, str]:
    """Guard da sincronização: autorização conhecida ou estado recuperável pós-transmissão.

    ``pode_consultar_situacao_sefaz`` continua estrito de propósito — Carta de Correção e
    Cancelamento o utilizam como pré-requisito e não podem ser liberados para NF-e rejeitada
    ou em erro de transmissão.
    """
    pode, motivo = pode_consultar_situacao_sefaz(nf)
    if pode:
        return True, ''
    if len(_chave_consulta(nf)) != 44:
        return False, MSG_SEM_CHAVE
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    if nf_cancelada_operacional(nf) or sefaz in _STATUS_TERMINAIS_SEM_SINCRONIZACAO:
        return False, MSG_STATUS_INCOMPATIVEL
    if _houve_tentativa_transmissao(nf):
        return True, ''
    return False, motivo


def _homologacao_da_nfe(nf: NFeSaida) -> bool:
    amb = (nf.ambiente_emissao or '').strip().lower()
    if amb == NFeSaida.AmbienteEmissao.PRODUCAO:
        return False
    if amb == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
        return True
    return nf_autorizada_homologacao(nf) or (
        (nf.status_emissao_sefaz or '').strip() == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
    )


def _situacao_inequivoca(resultado: ResultadoConsultaSituacaoSefaz) -> str:
    """cStat do documento (protNFe/infProt) — nunca o cStat da própria consulta.

    ``retConsSitNFe`` devolve ``cStat=100`` sempre que a consulta é aceita, inclusive quando a
    NF-e está em digitação ou não localizada (sem protocolo). Usar o fallback do parser
    marcaria como autorizada uma nota que a SEFAZ nunca autorizou.
    """
    return (resultado.c_stat_nfe or '').strip()


def _sincronizar_status_local_inequivoco(nf: NFeSaida, resultado: ResultadoConsultaSituacaoSefaz) -> bool:
    """Atualiza status local somente quando a SEFAZ indica situação inequívoca do documento."""
    cstat = _situacao_inequivoca(resultado)
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
        # Causa raiz do incidente: a SEFAZ autorizava, o protocolo era recuperado aqui e o
        # campo principal ``status`` continuava RASCUNHO — só o ramo CANCELADO o gravava.
        alvo_status = (
            NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO if homolog else 'AUTORIZADA_PRODUCAO'
        )
        if (nf.status or '').strip().upper() != alvo_status and not nf_cancelada_operacional(nf):
            nf.status = alvo_status
            update_fields.append('status')
        # Data da autorização: usa o dhRecbto da SEFAZ e só preenche se estiver vazia
        # (nota já autorizada não tem sua data reescrita por uma consulta posterior).
        if nf.autorizada_em is None:
            nf.autorizada_em = _parse_dh_recbto(resultado.dh_recbto) or timezone.now()
            update_fields.append('autorizada_em')
        # Guarda o retConsSitNFe da autorização quando o XML gravado não traz este protocolo
        # (ex.: rejeição 204) — é ele que permite remontar o procNFe e liberar DANFE/CR.
        if resultado.xml_retorno and not _xml_contem_protocolo(nf.xml_retorno, resultado.protocolo):
            nf.xml_retorno = resultado.xml_retorno
            update_fields.append('xml_retorno')
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
    pode, motivo = pode_sincronizar_com_sefaz(nf)
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

    status_anterior = nf.status or ''
    status_atualizado = _sincronizar_status_local_inequivoco(nf, resultado)
    nf.refresh_from_db()
    xml_autorizado_recuperado = _recuperar_xml_autorizado(nf, status_atualizado=status_atualizado)

    consultado_em = timezone.now()
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.CONSULTA_SITUACAO_SEFAZ,
        status_anterior=status_anterior,
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
        'CONSULTA_SITUACAO_SEFAZ_OK nfe_id=%s cStat=%s protocolo=%s status_atualizado=%s status=%s',
        nf.pk,
        resultado.c_stat,
        resultado.protocolo,
        status_atualizado,
        nf.status,
    )

    financeiro = _gerar_contas_receber_se_autorizada_producao(nf, usuario=usuario)

    extras: dict[str, Any] = {
        'status': nf.status or '',
        'xml_autorizado_recuperado': xml_autorizado_recuperado,
    }
    if financeiro is not None:
        extras['financeiro'] = financeiro

    return montar_resposta_consulta_situacao(
        nf,
        resultado,
        ok=resultado.ok,
        status_local_atualizado=status_atualizado,
        extras=extras,
    )


def _alinhar_ultimo_numero_autorizado(nf: NFeSaida) -> bool:
    """Registra na numeração o número cuja autorização acabou de ser recuperada.

    Não retrocede: recuperar uma nota antiga não pode fazer a próxima emissão repetir ou
    pular número já autorizado.
    """
    if (nf.status_emissao_sefaz or '') != NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
        return False
    try:
        numero = int((nf.numero_nfe or '').strip())
    except ValueError:
        return False
    cfg = NFeNumeracaoConfiguracao.objects.filter(
        empresa_id=resolver_empresa_emitente_nfe(nf).pk,
        ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
        modelo_documento='55',
        tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        serie=nf.serie_nfe,
        ativo=True,
    ).first()
    if cfg is None or (cfg.ultimo_numero_autorizado or 0) >= numero:
        return False
    cfg.ultimo_numero_autorizado = numero
    cfg.save(update_fields=['ultimo_numero_autorizado', 'atualizado_em'])
    logger.info(
        'NUMERACAO_ALINHADA_POS_AUTORIZACAO nfe_id=%s serie=%s numero=%s',
        nf.pk,
        nf.serie_nfe,
        numero,
    )
    return True


def recuperar_situacao_pos_rejeicao_duplicidade(
    nf: NFeSaida,
    *,
    usuario=None,
) -> dict[str, Any] | None:
    """Rejeição 204: a SEFAZ já tem este documento — consulta a situação para recuperar o protocolo.

    Retorna ``None`` quando a rejeição não é de duplicidade (fluxo normal de correção do XML).
    """
    if (nf.cstat_autorizacao or '').strip() != CSTAT_REJEICAO_DUPLICIDADE:
        return None
    resumo = consultar_situacao_nfe_saida(nf, usuario=usuario)
    resumo['mensagem'] = MSG_SEFAZ_JA_REGISTROU
    nf.refresh_from_db()
    _alinhar_ultimo_numero_autorizado(nf)
    return resumo


def _recuperar_xml_autorizado(nf: NFeSaida, *, status_atualizado: bool) -> bool:
    """Reconstrói ``xml_autorizado`` (DANFE/CR o exigem) quando só o protocolo foi recuperado."""
    if not status_atualizado or nf_tem_xml_autorizado_local(nf):
        return False
    if (nf.status_emissao_sefaz or '') not in (
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
    ):
        return False
    from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe

    try:
        resolver_xml_autorizado_danfe(nf, persistir=True)
    except Exception:
        logger.warning(
            'CONSULTA_SITUACAO_SEFAZ_SEM_XML_AUTORIZADO nfe_id=%s — protocolo recuperado, procNFe não montado.',
            nf.pk,
            exc_info=True,
        )
        return False
    return nf_tem_xml_autorizado_local(nf)


def _gerar_contas_receber_se_autorizada_producao(
    nf: NFeSaida,
    *,
    usuario=None,
) -> dict[str, Any] | None:
    """Dispara o CR quando a NF-e está autorizada em produção após a consulta.

    A rotina é idempotente e soft-fail: uma consulta posterior volta a tentar um CR que tenha
    falado na primeira sincronização, sem nunca duplicar título.
    """
    if (nf.status_emissao_sefaz or '') != NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
        return None
    from apps.fiscal.nfe_saida_financeiro import (
        gerar_contas_receber_automatico_apos_autorizacao_producao,
    )

    return gerar_contas_receber_automatico_apos_autorizacao_producao(nf, usuario=usuario)


# ============================================================================
# Consulta situação — NF-e de Entrada Própria (não emite, não cancela)
# ============================================================================


def _lock_nfe_entrada(nfe_id: int) -> NFeEntrada:
    return NFeEntrada.objects.select_for_update().get(pk=nfe_id)


def pode_consultar_situacao_sefaz_entrada(nf: NFeEntrada) -> tuple[bool, str]:
    """Permite consulta com chave válida, exceto em estados terminais (inutilizada/cancelada).

    Diferente da saída, a entrada aceita consulta em REJEITADA_* — é exatamente o
    caso onde a resposta SEFAZ se perdeu e o status local ficou errado.
    """
    chave = (nf.chave_acesso or '').strip()
    if len(chave) != 44:
        return False, MSG_SEM_CHAVE
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    if sefaz.startswith('INUTILIZADA') or sefaz.startswith('CANCELADA'):
        return False, MSG_STATUS_INCOMPATIVEL
    return True, ''


def _homologacao_da_nfe_entrada(nf: NFeEntrada) -> bool:
    return (nf.ambiente_emissao or '').strip().lower() == 'homologacao'


def _sincronizar_status_local_entrada(nf: NFeEntrada, resultado: ResultadoConsultaSituacaoSefaz) -> bool:
    """Atualiza status local da entrada quando a SEFAZ indica situação inequívoca do documento."""
    cstat = _situacao_inequivoca(resultado)
    if not cstat:
        return False

    update_fields: list[str] = []
    sefaz_ant = nf.status_emissao_sefaz or ''
    op_ant = nf.status_operacional or ''
    homolog = _homologacao_da_nfe_entrada(nf)

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
        alvo_sefaz = (
            NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
            if homolog
            else NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
        )
        alvo_op = (
            NFeEntrada.StatusOperacional.AUTORIZADA_HOMOLOGACAO
            if homolog
            else NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO
        )
        if sefaz_ant != alvo_sefaz:
            nf.status_emissao_sefaz = alvo_sefaz
            update_fields.append('status_emissao_sefaz')
        if op_ant != alvo_op:
            nf.status_operacional = alvo_op
            update_fields.append('status_operacional')
    elif cstat in CSTAT_CANCELADO:
        nf.cstat_autorizacao = cstat
        nf.motivo_autorizacao = resultado.x_motivo or nf.motivo_autorizacao
        update_fields.extend(['cstat_autorizacao', 'motivo_autorizacao'])
        alvo_sefaz = (
            NFeEntrada.StatusEmissaoSefaz.CANCELADA_HOMOLOGACAO
            if homolog
            else NFeEntrada.StatusEmissaoSefaz.CANCELADA_PRODUCAO
        )
        alvo_op = (
            NFeEntrada.StatusOperacional.CANCELADA_HOMOLOGACAO
            if homolog
            else NFeEntrada.StatusOperacional.CANCELADA_PRODUCAO
        )
        if sefaz_ant != alvo_sefaz:
            nf.status_emissao_sefaz = alvo_sefaz
            update_fields.append('status_emissao_sefaz')
        if op_ant != alvo_op:
            nf.status_operacional = alvo_op
            update_fields.append('status_operacional')
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
def consulta_situacao_nfe_entrada(nfe_entrada: NFeEntrada, *, usuario=None) -> dict[str, Any]:
    nf = _lock_nfe_entrada(nfe_entrada.pk)
    pode, motivo = pode_consultar_situacao_sefaz_entrada(nf)
    if not pode:
        raise NFeConsultaSituacaoError(motivo)

    chave = (nf.chave_acesso or '').strip()
    empresa = resolver_empresa_emitente_nfe(nf)
    homolog = _homologacao_da_nfe_entrada(nf)
    ambiente_label = 'homologacao' if homolog else 'producao'

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeConsultaSituacaoError(str(exc), etapa='CERTIFICADO') from exc

    senha = (empresa.senha_certificado or '').strip()
    uf = (empresa.uf or 'SP').strip()

    logger.info(
        'CONSULTA_SITUACAO_SEFAZ_ENTRADA_INICIO nfe_id=%s chave=%s ambiente=%s',
        nf.pk, chave, ambiente_label,
    )

    try:
        comunicacao = criar_comunicacao_sefaz(uf, cert.caminho, senha, homologacao=homolog)
        resposta_bruta = consulta_situacao_nfe(comunicacao, chave)
        xml_retorno = extrair_xml_resposta(resposta_bruta)
        resultado = parse_consulta_situacao_resposta(xml_retorno)
    except PyNFeComunicacaoError as exc:
        logger.warning('CONSULTA_SITUACAO_SEFAZ_ENTRADA_ERRO nfe_id=%s msg=%s', nf.pk, exc)
        raise NFeConsultaSituacaoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc

    status_atualizado = _sincronizar_status_local_entrada(nf, resultado)
    nf.refresh_from_db()

    logger.info(
        'CONSULTA_SITUACAO_SEFAZ_ENTRADA_OK nfe_id=%s cStat=%s protocolo=%s status_atualizado=%s',
        nf.pk, resultado.c_stat, resultado.protocolo, status_atualizado,
    )

    payload = montar_resposta_consulta_situacao(
        nf, resultado, ok=resultado.ok, status_local_atualizado=status_atualizado,
    )
    payload['nfe_entrada_id'] = nf.pk
    payload.pop('nfe_saida_id', None)
    return payload
