"""Orquestração da emissão NF-e entrada própria em homologação SEFAZ."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.fiscal.models import NFeEntrada
from apps.fiscal.nfe_emissao.assinatura import NFeAssinaturaError, assinar_xml_nfe
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_xml
from apps.fiscal.nfe_emissao.schema_validacao import validar_emissao_completa
from apps.fiscal.nfe_emissao.transmissao import NFeTransmissaoError, transmitir_nfe_homologacao
from apps.fiscal.nfe_entrada_emissao.aplicar_resultado import (
    aplicar_resultado_sefaz_homologacao_entrada,
    mensagem_resposta_resultado_entrada,
)
from apps.fiscal.nfe_entrada_emissao.numeracao import _lock_nfe_entrada, reservar_numeracao_nfe_entrada
from apps.fiscal.nfe_entrada_emissao.resposta_emissao import montar_resposta_emissao_entrada
from apps.fiscal.nfe_entrada_emissao.validacao import (
    NFeEntradaEmissaoValidationError,
    exigir_pronta_ou_erro,
    validar_pre_emissao_homologacao_entrada,
)
from apps.fiscal.nfe_entrada_emissao.xml_oficial import NFeEntradaXmlError, gerar_bytes_xml_oficial_nfe_entrada

logger = logging.getLogger(__name__)


class NFeEntradaEmissaoHomologacaoError(ValueError):
    def __init__(self, mensagem: str, *, detalhes: dict | None = None, etapa: str = ''):
        self.detalhes = detalhes or {}
        self.etapa = etapa or self.detalhes.get('etapa', '')
        super().__init__(mensagem)


def _montar_envio_lote(nf: NFeEntrada, xml_assinado: str) -> str:
    return montar_envi_nfe_xml(xml_assinado, id_lote=int(nf.pk), ind_sinc=1)


def _gerar_assinar_validar_xml(nf: NFeEntrada, empresa, *, usuario=None) -> tuple[str, str, str]:
    del usuario
    xml_bytes = gerar_bytes_xml_oficial_nfe_entrada(nf)
    xml_pre = xml_bytes.decode('utf-8')
    nf.xml_nfe_gerado = xml_pre
    nf.empresa_emitente = empresa
    nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.HOMOLOGACAO
    nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.XML_GERADO
    nf.save(
        update_fields=[
            'xml_nfe_gerado',
            'empresa_emitente',
            'ambiente_emissao',
            'status_emissao_sefaz',
        ],
    )

    assinado_bytes = assinar_xml_nfe(xml_bytes, empresa, nfe_saida=None)
    xml_assinado = assinado_bytes.decode('utf-8')
    xml_envio_lote = _montar_envio_lote(nf, xml_assinado)

    validacao_xsd = validar_emissao_completa(
        xml_assinado,
        xml_envio_lote,
        validar_assinado=True,
        xml_pre_assinatura=xml_pre,
    )
    if not validacao_xsd.get('ok'):
        tipo_val = validacao_xsd.get('tipo') or ''
        if tipo_val == 'CARACTERES_EDICAO':
            msg_bloqueio = (
                'XML contém caracteres de edição (BOM/whitespace entre tags). '
                'Compacte antes de transmitir (rejeição SEFAZ cStat 588).'
            )
            etapa = 'VALIDACAO_CARACTERES_EDICAO'
        else:
            msg_bloqueio = 'Falha na validação XSD local antes da transmissão.'
            etapa = 'VALIDACAO_XSD'
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.ERRO_TRANSMISSAO
        nf.motivo_autorizacao = msg_bloqueio
        nf.cstat_autorizacao = ''
        nf.xml_assinado = xml_assinado
        nf.xml_envio_lote = xml_envio_lote
        nf.status_operacional = NFeEntrada.StatusOperacional.ERRO_TRANSMISSAO
        nf.save(
            update_fields=[
                'status_emissao_sefaz',
                'motivo_autorizacao',
                'cstat_autorizacao',
                'xml_assinado',
                'xml_envio_lote',
                'status_operacional',
            ],
        )
        raise NFeEntradaEmissaoHomologacaoError(
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
    nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.XML_ASSINADO
    nf.save(update_fields=['xml_assinado', 'xml_envio_lote', 'status_emissao_sefaz'])
    return xml_pre, xml_assinado, xml_envio_lote


def emitir_nfe_entrada_homologacao(nf_entrada: NFeEntrada, *, usuario=None) -> dict[str, Any]:
    """Fluxo: validar → reservar → XML → assinar → transmitir homologação."""
    logger.info(
        'EMISSAO_ENTRADA_HOMOLOG_INICIO nf_id=%s empresa_emitente_id=%s',
        nf_entrada.pk,
        nf_entrada.empresa_emitente_id,
    )
    try:
        exigir_pronta_ou_erro(validar_pre_emissao_homologacao_entrada(nf_entrada, exigir_numeracao=False))
    except NFeEntradaEmissaoValidationError as exc:
        raise NFeEntradaEmissaoHomologacaoError(str(exc), detalhes={'erros': [str(exc)]}) from exc

    if not nf_entrada.empresa_emitente_id:
        raise NFeEntradaEmissaoHomologacaoError('Empresa emitente obrigatória.')

    try:
        with transaction.atomic():
            nf = _lock_nfe_entrada(nf_entrada.pk)
            if nf.status_emissao_sefaz == NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
                raise NFeEntradaEmissaoHomologacaoError('NF-e já autorizada em homologação.')

            nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.HOMOLOGACAO
            nf.save(update_fields=['ambiente_emissao'])

            if not (nf.numero_nfe and nf.serie_nfe and nf.chave_acesso):
                reservar_numeracao_nfe_entrada(nf, usuario=usuario)
                nf.refresh_from_db()

            empresa = nf.empresa_emitente
            _gerar_assinar_validar_xml(nf, empresa, usuario=usuario)

    except NFeEntradaEmissaoHomologacaoError:
        raise
    except (NFeEntradaXmlError, NFeAssinaturaError) as exc:
        raise NFeEntradaEmissaoHomologacaoError(str(exc), detalhes={'erros': [str(exc)]}) from exc

    nf = NFeEntrada.objects.get(pk=nf_entrada.pk)
    empresa = nf.empresa_emitente

    try:
        # Duck-type: transmissao usa pk/serie/numero/chave/ambiente — compatível com NFeEntrada.
        resultado = transmitir_nfe_homologacao(nf, nf.xml_assinado, empresa)  # type: ignore[arg-type]
    except NFeTransmissaoError as exc:
        etapa = getattr(exc, 'etapa', 'TRANSMISSAO_SEFAZ') or 'TRANSMISSAO_SEFAZ'
        with transaction.atomic():
            nf = _lock_nfe_entrada(nf.pk)
            nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.ERRO_TRANSMISSAO
            nf.status_operacional = NFeEntrada.StatusOperacional.ERRO_TRANSMISSAO
            nf.motivo_autorizacao = str(exc)
            nf.cstat_autorizacao = ''
            nf.save(
                update_fields=[
                    'status_emissao_sefaz',
                    'status_operacional',
                    'motivo_autorizacao',
                    'cstat_autorizacao',
                ],
            )
        raise NFeEntradaEmissaoHomologacaoError(
            'Falha técnica ao transmitir NF-e entrada em homologação.',
            detalhes={'erros': [str(exc)], 'etapa': etapa},
            etapa=etapa,
        ) from exc

    with transaction.atomic():
        nf = _lock_nfe_entrada(nf.pk)
        nf = aplicar_resultado_sefaz_homologacao_entrada(
            nf,
            resultado,
            empresa=empresa,
            usuario=usuario,
            xml_envio=nf.xml_envio_lote or nf.xml_assinado or '',
        )

    nf.refresh_from_db()
    logger.info(
        'EMISSAO_ENTRADA_HOMOLOG_FIM nf_id=%s autorizado=%s cStat=%s',
        nf.pk,
        resultado.autorizado,
        nf.cstat_autorizacao,
    )
    return montar_resposta_emissao_entrada(
        nf,
        ok=resultado.autorizado or resultado.rejeitado,
        ambiente='homologacao',
        autorizado=resultado.autorizado,
        mensagem=mensagem_resposta_resultado_entrada(resultado),
        resultado=resultado,
    )
