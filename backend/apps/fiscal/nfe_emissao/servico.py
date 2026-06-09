"""Orquestração da emissão NF-e em homologação SEFAZ."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.assinatura import NFeAssinaturaError, assinar_xml_nfe
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.transmissao import NFeTransmissaoError, transmitir_nfe_homologacao
from apps.fiscal.nfe_emissao.resposta import montar_resposta_emissao_homologacao
from apps.fiscal.nfe_emissao.validacao import NFeEmissaoValidacaoError, validar_pre_emissao_homologacao
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_xml
from apps.fiscal.nfe_emissao.schema_validacao import validar_emissao_completa
from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError, gerar_xml_oficial_emissao
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)

from apps.fiscal.nfe_emissao.aplicar_resultado import (
    MSG_SEM_EFEITOS_REAIS,
    aplicar_resultado_sefaz_homologacao,
    mensagem_resposta_resultado,
    resultado_tem_resolucao_final,
)
from apps.fiscal.nfe_emissao.retorno_sefaz import processar_retorno_autorizacao_nfe


logger = logging.getLogger(__name__)


def _pode_reprocessar_retorno_salvo(nf: NFeSaida) -> bool:
    if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        return False
    xml = (nf.xml_retorno or nf.xml_retorno_lote or '').strip()
    if not xml:
        return False
    cstat_nfe = (nf.cstat_autorizacao or '').strip()
    if cstat_nfe and cstat_nfe not in ('104', ''):
        return False
    if nf.cstat_lote == '104' and cstat_nfe in ('104', ''):
        return True
    if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO and cstat_nfe == '104':
        return True
    return nf.status_emissao_sefaz in (
        'LOTE_PROCESSADO_SEM_PROTOCOLO',
    )


@transaction.atomic
def reprocessar_retorno_nfe_homologacao(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    """Reinterpreta xml_retorno salvo (ex.: lote 104 + infProt) sem retransmitir."""
    nf = _lock_nfe_saida(nfe_saida.pk)
    xml = (nf.xml_retorno or nf.xml_retorno_lote or '').strip()
    if not xml:
        raise NFeEmissaoHomologacaoError('Nenhum XML de retorno SEFAZ salvo para reprocessar.')
    if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        raise NFeEmissaoHomologacaoError('NF-e já autorizada em homologação.')

    empresa = resolver_empresa_emitente_nfe(nf)
    logger.info('REPROCESSAR_RETORNO_SEFAZ nfe_id=%s chave=%s', nf.pk, nf.chave_acesso)
    resultado = processar_retorno_autorizacao_nfe(xml, nf, xml_assinado=nf.xml_assinado or '')
    nf = aplicar_resultado_sefaz_homologacao(
        nf,
        resultado,
        empresa=empresa,
        usuario=usuario,
        xml_envio=nf.xml_envio or nf.xml_assinado or '',
    )
    ok = resultado.autorizado
    return montar_resposta_emissao_homologacao(
        nf,
        ok=ok,
        autorizado=resultado.autorizado,
        mensagem=mensagem_resposta_resultado(resultado),
        resultado=resultado,
    )


class NFeEmissaoHomologacaoError(ValueError):
    def __init__(self, mensagem: str, *, detalhes: dict | None = None, etapa: str = ''):
        self.detalhes = detalhes or {}
        self.etapa = etapa or self.detalhes.get('etapa', '')
        super().__init__(mensagem)


def _montar_envio_lote(nf: NFeSaida, xml_assinado: str) -> str:
    return montar_envi_nfe_xml(xml_assinado, id_lote=int(nf.pk), ind_sinc=1)


def _validar_xmls_antes_transmissao(
    nf: NFeSaida,
    xml_assinado: str,
    xml_envio_lote: str,
    *,
    xml_pre: str = '',
) -> dict[str, Any]:
    resultado = validar_emissao_completa(
        xml_assinado,
        xml_envio_lote,
        validar_assinado=True,
        xml_pre_assinatura=xml_pre or nf.xml_nfe_gerado or '',
    )
    if not resultado.get('ok'):
        logger.warning(
            'VALIDACAO_PRE_TRANSMISSAO_FALHOU nfe_id=%s tipo=%s erros=%s',
            nf.pk,
            resultado.get('tipo'),
            len(resultado.get('erros') or []),
        )
    return resultado


def _gerar_assinar_validar_xml_emissao(
    nf: NFeSaida,
    empresa,
    *,
    usuario=None,
) -> tuple[str, str, str]:
    """Retorna (xml_pre, xml_assinado, xml_envio_lote) após validação XSD."""
    xml_bytes = gerar_xml_oficial_emissao(nf)
    xml_pre = xml_bytes.decode('utf-8')
    nf.xml_nfe_gerado = xml_pre
    nf.empresa_emitente = empresa
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_GERADO
    nf.save(
        update_fields=[
            'xml_nfe_gerado',
            'empresa_emitente',
            'ambiente_emissao',
            'status_emissao_sefaz',
        ],
    )
    logger.info('XML_OFICIAL_GERADO nfe_id=%s chave=%s', nf.pk, nf.chave_acesso)
    _registrar_evento(
        nf,
        tipo='XML_OFICIAL_GERADO',
        status_novo=nf.status_emissao_sefaz,
        resumo={'chave_acesso': nf.chave_acesso},
        usuario=usuario,
    )

    assinado_bytes = assinar_xml_nfe(xml_bytes, empresa, nfe_saida=nf)
    xml_assinado = assinado_bytes.decode('utf-8')
    xml_envio_lote = _montar_envio_lote(nf, xml_assinado)

    validacao_xsd = _validar_xmls_antes_transmissao(
        nf,
        xml_assinado,
        xml_envio_lote,
        xml_pre=xml_pre,
    )
    if not validacao_xsd.get('ok'):
        tipo_val = validacao_xsd.get('tipo') or ''
        if tipo_val == 'CARACTERES_EDICAO':
            msg_bloqueio = (
                'XML contém caracteres de edição (BOM/whitespace entre tags). '
                'Compacte antes de transmitir (rejeição SEFAZ cStat 588).'
            )
            etapa = 'VALIDACAO_CARACTERES_EDICAO'
            evento = 'VALIDACAO_CARACTERES_EDICAO_BLOQUEIO'
        else:
            msg_bloqueio = 'Falha na validação XSD local antes da transmissão.'
            etapa = 'VALIDACAO_XSD'
            evento = 'VALIDACAO_XSD_BLOQUEIO'
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
        nf.motivo_autorizacao = msg_bloqueio
        nf.cstat_autorizacao = ''
        nf.xml_assinado = xml_assinado
        nf.xml_envio_lote = xml_envio_lote
        nf.save(
            update_fields=[
                'status_emissao_sefaz',
                'motivo_autorizacao',
                'cstat_autorizacao',
                'xml_assinado',
                'xml_envio_lote',
            ],
        )
        _registrar_evento(
            nf,
            tipo=evento,
            status_novo=nf.status_emissao_sefaz,
            resumo={
                'tipo': validacao_xsd.get('tipo'),
                'erros': (validacao_xsd.get('erros') or [])[:5],
            },
            observacao=msg_bloqueio,
            usuario=usuario,
        )
        raise NFeEmissaoHomologacaoError(
            msg_bloqueio,
            detalhes={
                'erros': validacao_xsd.get('erros') or [],
                'validacao_xsd': validacao_xsd,
                'etapa': etapa,
            },
            etapa=etapa,
        )

    nf.xml_assinado = xml_assinado
    nf.xml_envio_lote = xml_envio_lote
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_ASSINADO
    nf.save(update_fields=['xml_assinado', 'xml_envio_lote', 'status_emissao_sefaz'])
    logger.info('XML_ASSINADO nfe_id=%s chave=%s', nf.pk, nf.chave_acesso)
    _registrar_evento(
        nf,
        tipo='XML_ASSINADO',
        status_novo=nf.status_emissao_sefaz,
        usuario=usuario,
    )
    return xml_pre, xml_assinado, xml_envio_lote


@transaction.atomic
def validar_xml_nfe_saida_schema(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    """Gera XML atual e valida localmente contra XSD (sem transmitir)."""
    nf = _lock_nfe_saida(nfe_saida.pk)
    if not nf.numero_nfe:
        raise NFeEmissaoHomologacaoError('Reserve a numeração antes de validar o XML.')
    empresa = resolver_empresa_emitente_nfe(nf)
    xml_bytes = gerar_xml_oficial_emissao(nf)
    xml_pre = xml_bytes.decode('utf-8')
    try:
        assinado = assinar_xml_nfe(xml_bytes, empresa, nfe_saida=nf).decode('utf-8')
    except NFeAssinaturaError:
        assinado = xml_pre
    xml_envio_lote = _montar_envio_lote(nf, assinado)
    validacao = _validar_xmls_antes_transmissao(nf, assinado, xml_envio_lote, xml_pre=xml_pre)
    nf.xml_nfe_gerado = xml_pre
    nf.xml_assinado = assinado
    nf.xml_envio_lote = xml_envio_lote
    nf.save(update_fields=['xml_nfe_gerado', 'xml_assinado', 'xml_envio_lote'])
    return {
        'nfe_saida_id': nf.pk,
        'ok': validacao.get('ok'),
        'tipo': validacao.get('tipo'),
        'erros': validacao.get('erros') or [],
        'schema_ok': validacao.get('schema_ok'),
        'compacto': validacao.get('compacto'),
        'validacoes': validacao.get('validacoes') or {},
    }


@transaction.atomic
def reservar_numeracao_nfe_saida(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    validar_pre_emissao_homologacao(nfe_saida)
    num = reservar_numeracao_nfe(
        nfe_saida,
        ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO,
        usuario=usuario,
    )
    nf = NFeSaida.objects.get(pk=nfe_saida.pk)
    return {
        'nfe_saida_id': nf.pk,
        'serie_nfe': num.serie,
        'numero_nfe': num.nnf,
        'chave_acesso': num.chave.chave_44,
        'ambiente_emissao': num.ambiente,
        'status_emissao_sefaz': nf.status_emissao_sefaz,
    }


@transaction.atomic
def gerar_xml_nfe_saida_oficial(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    if not nf.numero_nfe:
        reservar_numeracao_nfe(nf, ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO, usuario=usuario)
        nf.refresh_from_db()

    xml_bytes = gerar_xml_oficial_emissao(nf)
    xml_str = xml_bytes.decode('utf-8')
    nf.xml_nfe_gerado = xml_str
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_GERADO
    nf.save(update_fields=['xml_nfe_gerado', 'status_emissao_sefaz'])
    _registrar_evento(
        nf,
        tipo='XML_OFICIAL_GERADO',
        status_novo=nf.status_emissao_sefaz,
        resumo={'chave_acesso': nf.chave_acesso, 'numero_nfe': nf.numero_nfe},
        observacao='XML oficial NF-e 4.00 gerado para emissão.',
        usuario=usuario,
    )
    return {'nfe_saida_id': nf.pk, 'xml': xml_str, 'status_emissao_sefaz': nf.status_emissao_sefaz}


@transaction.atomic
def assinar_xml_nfe_saida(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    nf = _lock_nfe_saida(nfe_saida.pk)
    if not nf.numero_nfe:
        raise NFeAssinaturaError('Reserve a numeração e gere o XML antes de assinar.')

    xml_bytes = gerar_xml_oficial_emissao(nf)
    empresa = resolver_empresa_emitente_nfe(nf)
    assinado = assinar_xml_nfe(xml_bytes, empresa, nfe_saida=nf)
    nf.xml_nfe_gerado = xml_bytes.decode('utf-8')
    nf.xml_assinado = assinado.decode('utf-8')
    nf.xml_envio_lote = _montar_envio_lote(nf, nf.xml_assinado)
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_ASSINADO
    nf.save(update_fields=['xml_nfe_gerado', 'xml_assinado', 'xml_envio_lote', 'status_emissao_sefaz'])
    _registrar_evento(
        nf,
        tipo='XML_ASSINADO',
        status_novo=nf.status_emissao_sefaz,
        resumo={'chave_acesso': nf.chave_acesso},
        observacao='XML NF-e assinado com certificado A1.',
        usuario=usuario,
    )
    return {'nfe_saida_id': nf.pk, 'status_emissao_sefaz': nf.status_emissao_sefaz}


def emitir_nfe_homologacao(nfe_saida: NFeSaida, *, usuario=None) -> dict[str, Any]:
    """
    Fluxo completo: validar → reservar → XML → assinar → transmitir homologação.
    Não aplica efeitos de estoque/financeiro reais.
    """
    logger.info(
        'EMISSAO_HOMOLOGACAO_INICIO nfe_id=%s empresa_emitente_id=%s ambiente=homologacao',
        nfe_saida.pk,
        nfe_saida.empresa_emitente_id,
    )
    try:
        validar_pre_emissao_homologacao(nfe_saida)
    except NFeEmissaoValidacaoError as exc:
        raise NFeEmissaoHomologacaoError(exc.mensagens[0], detalhes={'erros': exc.mensagens}) from exc

    empresa_prev = resolver_empresa_emitente_nfe(nfe_saida)
    with transaction.atomic():
        nf_evt = _lock_nfe_saida(nfe_saida.pk)
        _registrar_evento(
            nf_evt,
            tipo='EMISSAO_HOMOLOGACAO_INICIADA',
            status_novo=nf_evt.status_emissao_sefaz,
            resumo={'ambiente': 'homologacao', 'empresa_id': empresa_prev.pk},
            observacao='Início da emissão NF-e em homologação SEFAZ.',
            usuario=usuario,
        )

    try:
        with transaction.atomic():
            nf = _lock_nfe_saida(nfe_saida.pk)
            if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
                raise NFeEmissaoHomologacaoError('NF-e já autorizada em homologação.')
            if nf.numero_nfe and nf.serie_nfe and nf.chave_acesso:
                logger.info(
                    'NUMERACAO_JA_RESERVADA nfe_id=%s serie=%s numero=%s chave=%s',
                    nf.pk,
                    nf.serie_nfe,
                    nf.numero_nfe,
                    nf.chave_acesso,
                )
                _registrar_evento(
                    nf,
                    tipo='NUMERACAO_RESERVADA',
                    status_novo=nf.status_emissao_sefaz,
                    resumo={
                        'serie': nf.serie_nfe,
                        'numero_nfe': nf.numero_nfe,
                        'chave_acesso': nf.chave_acesso,
                        'ambiente': 'homologacao',
                        'reutilizada': True,
                    },
                    observacao='Numeração já reservada — reutilizada no retry.',
                    usuario=usuario,
                )
            elif not nf.numero_nfe:
                reservar_numeracao_nfe(
                    nf,
                    ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO,
                    usuario=usuario,
                )
                nf.refresh_from_db()
                logger.info(
                    'NUMERACAO_RESERVADA nfe_id=%s serie=%s numero=%s chave=%s',
                    nf.pk,
                    nf.serie_nfe,
                    nf.numero_nfe,
                    nf.chave_acesso,
                )

            xml_pre, xml_assinado, xml_envio_lote = _gerar_assinar_validar_xml_emissao(
                nf,
                resolver_empresa_emitente_nfe(nf),
                usuario=usuario,
            )
            _ = xml_pre, xml_assinado, xml_envio_lote

    except NFeEmissaoHomologacaoError as exc:
        det = getattr(exc, 'detalhes', None) or {}
        etapa = str(det.get('etapa') or getattr(exc, 'etapa', '') or '')
        if etapa in ('VALIDACAO_XSD', 'VALIDACAO_CARACTERES_EDICAO'):
            with transaction.atomic():
                nf_err = _lock_nfe_saida(nfe_saida.pk)
                nf_err.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
                nf_err.motivo_autorizacao = str(exc)
                nf_err.cstat_autorizacao = ''
                nf_err.save(update_fields=['status_emissao_sefaz', 'motivo_autorizacao', 'cstat_autorizacao'])
                _registrar_evento(
                    nf_err,
                    tipo='VALIDACAO_XSD_BLOQUEIO' if etapa == 'VALIDACAO_XSD' else 'VALIDACAO_CARACTERES_EDICAO_BLOQUEIO',
                    status_novo=nf_err.status_emissao_sefaz,
                    resumo={'etapa': etapa, 'erros': (det.get('erros') or [])[:5]},
                    observacao=str(exc),
                    usuario=usuario,
                )
        raise

    nf = NFeSaida.objects.get(pk=nfe_saida.pk)
    empresa = resolver_empresa_emitente_nfe(nf)

    if _pode_reprocessar_retorno_salvo(nf):
        logger.info('REPROCESSAR_RETORNO_ANTES_RETRANSMITIR nfe_id=%s', nf.pk)
        try:
            return reprocessar_retorno_nfe_homologacao(nf, usuario=usuario)
        except NFeEmissaoHomologacaoError:
            pass

    try:
        resultado = transmitir_nfe_homologacao(nf, nf.xml_assinado, empresa)
    except NFeTransmissaoError as exc:
        etapa = getattr(exc, 'etapa', 'TRANSMISSAO_SEFAZ') or 'TRANSMISSAO_SEFAZ'
        with transaction.atomic():
            nf = _lock_nfe_saida(nf.pk)
            nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO
            nf.motivo_autorizacao = str(exc)
            nf.cstat_autorizacao = ''
            nf.save(update_fields=['status_emissao_sefaz', 'motivo_autorizacao', 'cstat_autorizacao'])
            _registrar_evento(
                nf,
                tipo='ERRO_TRANSMISSAO_SEFAZ',
                status_novo=nf.status_emissao_sefaz,
                resumo={
                    'etapa': etapa,
                    'erro': str(exc),
                    'serie': nf.serie_nfe,
                    'numero_nfe': nf.numero_nfe,
                    'chave_acesso': nf.chave_acesso,
                },
                observacao=str(exc),
                usuario=usuario,
            )
        logger.exception(
            'ERRO_TRANSMISSAO nfe_id=%s empresa_id=%s ambiente=homologacao serie=%s numero=%s chave=%s etapa=%s',
            nf.pk,
            empresa.pk,
            nf.serie_nfe,
            nf.numero_nfe,
            nf.chave_acesso,
            etapa,
        )
        raise NFeEmissaoHomologacaoError(
            'Falha técnica ao transmitir NF-e em homologação.',
            detalhes={'erros': [str(exc)], 'etapa': etapa},
            etapa=etapa,
        ) from exc

    with transaction.atomic():
        nf = _lock_nfe_saida(nf.pk)
        nf = aplicar_resultado_sefaz_homologacao(
            nf,
            resultado,
            empresa=empresa,
            usuario=usuario,
            xml_envio=nf.xml_envio_lote or nf.xml_assinado or '',
        )

    nf.refresh_from_db()
    logger.info(
        'Emissão homologação concluída nfe_id=%s autorizado=%s cStat_lote=%s cStat_nfe=%s serie=%s numero=%s',
        nf.pk,
        resultado.autorizado,
        resultado.lote.c_stat,
        nf.cstat_autorizacao,
        nf.serie_nfe,
        nf.numero_nfe,
    )
    ok = resultado.autorizado or (
        resultado_tem_resolucao_final(resultado)
        and resultado.status_final not in ('ERRO_RETORNO_SEFAZ', 'LOTE_PROCESSADO_SEM_PROTOCOLO')
    )
    return montar_resposta_emissao_homologacao(
        nf,
        ok=ok,
        autorizado=resultado.autorizado,
        mensagem=mensagem_resposta_resultado(resultado),
        resultado=resultado,
        extras={'status': nf.status},
    )
