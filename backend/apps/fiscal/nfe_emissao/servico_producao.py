"""Orquestração da emissão NF-e Saída em produção SEFAZ (Fase 3B)."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.aplicar_resultado import (
    MSG_SEM_EFEITOS_PRODUCAO,
    aplicar_resultado_sefaz_producao,
    mensagem_resposta_resultado_producao,
    resultado_tem_resolucao_final,
)
from apps.fiscal.nfe_emissao.assinatura import NFeAssinaturaError, assinar_xml_nfe
from apps.fiscal.nfe_emissao.config_producao import (
    exigir_producao_habilitada,
    validar_confirmacao_emissao_producao,
)
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_xml
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.resposta_producao import montar_resposta_emissao_producao
from apps.fiscal.nfe_emissao.schema_validacao import validar_emissao_completa
from apps.fiscal.nfe_emissao.transmissao_producao import NFeTransmissaoProducaoError, transmitir_nfe_producao
from apps.fiscal.nfe_emissao.validacao import NFeEmissaoValidacaoError
from apps.fiscal.nfe_emissao.validacao_producao import (
    validar_pre_emissao_producao,
    validar_xml_emissao_producao_local,
)
from apps.fiscal.nfe_emissao.xsd_erros import resumo_erros_xsd_log
from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError, gerar_xml_oficial_emissao
from apps.fiscal.nfe_saida_efeitos import _lock_nfe_saida, _registrar_evento

logger = logging.getLogger(__name__)


class NFeEmissaoProducaoError(ValueError):
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
            'VALIDACAO_PRE_TRANSMISSAO_PRODUCAO_FALHOU nfe_id=%s tipo=%s erros=%s detalhe=%s',
            nf.pk,
            resultado.get('tipo'),
            len(resultado.get('erros') or []),
            resumo_erros_xsd_log(resultado.get('erros') or []),
        )
    return resultado


def _gerar_assinar_validar_xml_emissao_producao(
    nf: NFeSaida,
    empresa,
    *,
    usuario=None,
) -> tuple[str, str, str]:
    xml_bytes = gerar_xml_oficial_emissao(nf)
    xml_pre = xml_bytes.decode('utf-8')
    erros_tpamb = validar_xml_emissao_producao_local(xml_pre, nfe_saida=nf)
    if erros_tpamb:
        raise NFeEmissaoProducaoError(
            erros_tpamb[0],
            detalhes={'erros': erros_tpamb, 'etapa': 'XML_PRODUCAO'},
            etapa='XML_PRODUCAO',
        )

    nf.xml_nfe_gerado = xml_pre
    nf.empresa_emitente = empresa
    nf.ambiente_emissao = NFeSaida.AmbienteEmissao.PRODUCAO
    nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_GERADO
    nf.save(
        update_fields=[
            'xml_nfe_gerado',
            'empresa_emitente',
            'ambiente_emissao',
            'status_emissao_sefaz',
        ],
    )
    logger.info('XML_OFICIAL_PRODUCAO_GERADO nfe_id=%s chave=%s', nf.pk, nf.chave_acesso)
    _registrar_evento(
        nf,
        tipo='XML_OFICIAL_GERADO',
        status_novo=nf.status_emissao_sefaz,
        resumo={'chave_acesso': nf.chave_acesso, 'ambiente': 'producao'},
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
            msg_bloqueio = 'Falha na validação XSD local antes da transmissão produção.'
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
                'ambiente': 'producao',
            },
            observacao=msg_bloqueio,
            usuario=usuario,
        )
        raise NFeEmissaoProducaoError(
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
    logger.info('XML_ASSINADO_PRODUCAO nfe_id=%s chave=%s', nf.pk, nf.chave_acesso)
    _registrar_evento(
        nf,
        tipo='XML_ASSINADO',
        status_novo=nf.status_emissao_sefaz,
        resumo={'ambiente': 'producao'},
        usuario=usuario,
    )
    return xml_pre, xml_assinado, xml_envio_lote


def emitir_nfe_producao(
    nfe_saida: NFeSaida,
    *,
    usuario=None,
    confirmacao_payload: dict | None = None,
) -> dict[str, Any]:
    """
    Fluxo completo produção: validar → reservar → XML tpAmb=1 → assinar → transmitir.
    Exige flag NFE_PRODUCAO_HABILITADA e confirmação explícita no payload.
    Não aplica estoque/financeiro/apuração automática.
    """
    exigir_producao_habilitada()
    from apps.fiscal.nfe_emissao.permissoes_producao import exigir_permissao_usuario_producao

    exigir_permissao_usuario_producao(usuario)
    validar_confirmacao_emissao_producao(confirmacao_payload)

    logger.info(
        'EMISSAO_PRODUCAO_INICIO nfe_id=%s empresa_emitente_id=%s ambiente=producao',
        nfe_saida.pk,
        nfe_saida.empresa_emitente_id,
    )
    try:
        validar_pre_emissao_producao(nfe_saida)
    except NFeEmissaoValidacaoError as exc:
        raise NFeEmissaoProducaoError(exc.mensagens[0], detalhes={'erros': exc.mensagens}) from exc

    empresa_prev = resolver_empresa_emitente_nfe(nfe_saida)
    with transaction.atomic():
        nf_evt = _lock_nfe_saida(nfe_saida.pk)
        _registrar_evento(
            nf_evt,
            tipo='EMISSAO_PRODUCAO_INICIADA',
            status_novo=nf_evt.status_emissao_sefaz,
            resumo={'ambiente': 'producao', 'empresa_id': empresa_prev.pk},
            observacao='Início da emissão NF-e em produção SEFAZ.',
            usuario=usuario,
        )

    try:
        with transaction.atomic():
            nf = _lock_nfe_saida(nfe_saida.pk)
            if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
                raise NFeEmissaoProducaoError('NF-e já autorizada em produção SEFAZ.')
            if nf.numero_nfe and nf.serie_nfe and nf.chave_acesso and nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO:
                _registrar_evento(
                    nf,
                    tipo='NUMERACAO_RESERVADA',
                    status_novo=nf.status_emissao_sefaz,
                    resumo={
                        'serie': nf.serie_nfe,
                        'numero_nfe': nf.numero_nfe,
                        'chave_acesso': nf.chave_acesso,
                        'ambiente': 'producao',
                        'reutilizada': True,
                    },
                    observacao='Numeração produção já reservada — reutilizada no retry.',
                    usuario=usuario,
                )
            elif not nf.numero_nfe or nf.ambiente_emissao != NFeSaida.AmbienteEmissao.PRODUCAO:
                reservar_numeracao_nfe(
                    nf,
                    ambiente=NFeSaida.AmbienteEmissao.PRODUCAO,
                    usuario=usuario,
                )
                nf.refresh_from_db()

            _gerar_assinar_validar_xml_emissao_producao(
                nf,
                resolver_empresa_emitente_nfe(nf),
                usuario=usuario,
            )

    except NFeEmissaoProducaoError:
        raise
    except (NFeNumeracaoError, NFeXmlEmissaoError, NFeAssinaturaError) as exc:
        raise NFeEmissaoProducaoError(str(exc), detalhes={'erros': [str(exc)]}) from exc

    nf = NFeSaida.objects.get(pk=nfe_saida.pk)
    empresa = resolver_empresa_emitente_nfe(nf)

    try:
        resultado = transmitir_nfe_producao(nf, nf.xml_assinado, empresa)
    except NFeTransmissaoProducaoError as exc:
        etapa = getattr(exc, 'etapa', 'TRANSMISSAO_SEFAZ_PRODUCAO') or 'TRANSMISSAO_SEFAZ_PRODUCAO'
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
                    'ambiente': 'producao',
                    'serie': nf.serie_nfe,
                    'numero_nfe': nf.numero_nfe,
                    'chave_acesso': nf.chave_acesso,
                },
                observacao=str(exc),
                usuario=usuario,
            )
        logger.exception(
            'ERRO_TRANSMISSAO_PRODUCAO nfe_id=%s empresa_id=%s serie=%s numero=%s chave=%s etapa=%s',
            nf.pk,
            empresa.pk,
            nf.serie_nfe,
            nf.numero_nfe,
            nf.chave_acesso,
            etapa,
        )
        raise NFeEmissaoProducaoError(
            'Falha técnica ao transmitir NF-e em produção SEFAZ.',
            detalhes={'erros': [str(exc)], 'etapa': etapa},
            etapa=etapa,
        ) from exc

    with transaction.atomic():
        nf = _lock_nfe_saida(nf.pk)
        nf = aplicar_resultado_sefaz_producao(
            nf,
            resultado,
            empresa=empresa,
            usuario=usuario,
            xml_envio=nf.xml_envio_lote or nf.xml_assinado or '',
        )

    nf.refresh_from_db()
    logger.info(
        'Emissão produção concluída nfe_id=%s autorizado=%s cStat_nfe=%s serie=%s numero=%s',
        nf.pk,
        resultado.autorizado,
        nf.cstat_autorizacao,
        nf.serie_nfe,
        nf.numero_nfe,
    )
    ok = resultado.autorizado or (
        resultado_tem_resolucao_final(resultado)
        and resultado.status_final not in ('ERRO_RETORNO_SEFAZ', 'LOTE_PROCESSADO_SEM_PROTOCOLO')
    )
    return montar_resposta_emissao_producao(
        nf,
        ok=ok,
        autorizado=resultado.autorizado,
        mensagem=mensagem_resposta_resultado_producao(resultado),
        resultado=resultado,
        extras={'status': nf.status, 'sem_efeitos_erp': True, 'mensagem_efeitos': MSG_SEM_EFEITOS_PRODUCAO},
    )
