"""Orquestração da emissão NF-e entrada própria em produção SEFAZ."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.fiscal.models import NFeEntrada
from apps.fiscal.nfe_emissao.assinatura import NFeAssinaturaError, assinar_xml_nfe
from apps.fiscal.nfe_emissao.config_producao import (
    exigir_producao_habilitada,
    validar_confirmacao_emissao_producao,
)
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_xml
from apps.fiscal.nfe_emissao.schema_validacao import validar_emissao_completa
from apps.fiscal.nfe_emissao.transmissao_producao import NFeTransmissaoProducaoError, transmitir_nfe_producao
from apps.fiscal.nfe_entrada_emissao.aplicar_resultado import (
    aplicar_resultado_sefaz_producao_entrada,
    mensagem_resposta_resultado_entrada,
)
from apps.fiscal.nfe_entrada_emissao.numeracao import _lock_nfe_entrada, reservar_numeracao_nfe_entrada
from apps.fiscal.nfe_entrada_emissao.resposta_emissao import montar_resposta_emissao_entrada
from apps.fiscal.nfe_entrada_emissao.validacao import (
    NFeEntradaEmissaoValidationError,
    exigir_pronta_ou_erro,
    validar_pre_emissao_producao_entrada,
)
from apps.fiscal.nfe_entrada_emissao.xml_oficial import NFeEntradaXmlError, gerar_bytes_xml_oficial_nfe_entrada

logger = logging.getLogger(__name__)


class NFeEntradaEmissaoProducaoError(ValueError):
    def __init__(self, mensagem: str, *, detalhes: dict | None = None, etapa: str = ''):
        self.detalhes = detalhes or {}
        self.etapa = etapa or self.detalhes.get('etapa', '')
        super().__init__(mensagem)


def _montar_envio_lote(nf: NFeEntrada, xml_assinado: str) -> str:
    return montar_envi_nfe_xml(xml_assinado, id_lote=int(nf.pk), ind_sinc=1)


def _gerar_assinar_validar_xml_producao(nf: NFeEntrada, empresa, *, usuario=None) -> tuple[str, str, str]:
    del usuario
    xml_bytes = gerar_bytes_xml_oficial_nfe_entrada(nf)
    xml_pre = xml_bytes.decode('utf-8')

    import re

    if not re.search(r'<[\w:]*tpAmb>\s*1\s*</[\w:]*tpAmb>', xml_pre):
        raise NFeEntradaEmissaoProducaoError(
            'XML de produção deve conter tpAmb=1.',
            detalhes={'erros': ['tpAmb inválido'], 'etapa': 'XML_PRODUCAO'},
            etapa='XML_PRODUCAO',
        )

    nf.xml_nfe_gerado = xml_pre
    nf.empresa_emitente = empresa
    nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.PRODUCAO
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
            msg_bloqueio = 'Falha na validação XSD local antes da transmissão produção.'
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
        raise NFeEntradaEmissaoProducaoError(
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


def emitir_nfe_entrada_producao(
    nf_entrada: NFeEntrada,
    *,
    usuario=None,
    confirmacao_payload: dict | None = None,
) -> dict[str, Any]:
    """Fluxo produção: flag + permissão + confirmação → validar → reservar → XML → SEFAZ."""
    exigir_producao_habilitada()
    from apps.fiscal.nfe_emissao.permissoes_producao import exigir_permissao_usuario_producao

    exigir_permissao_usuario_producao(usuario)
    validar_confirmacao_emissao_producao(confirmacao_payload)

    logger.info(
        'EMISSAO_ENTRADA_PRODUCAO_INICIO nf_id=%s empresa_emitente_id=%s',
        nf_entrada.pk,
        nf_entrada.empresa_emitente_id,
    )

    # Garante ambiente produção antes da validação (ainda sem numeração).
    # Se reservou em homologação sem SEFAZ, desfaz e prepara a mesma NF.
    from apps.fiscal.nfe_entrada_emissao.preparar_producao import (
        NFeEntradaPrepararProducaoError,
        precisa_preparar_para_producao,
        preparar_entrada_para_producao,
    )

    if precisa_preparar_para_producao(nf_entrada):
        try:
            preparar_entrada_para_producao(nf_entrada, usuario=usuario)
            nf_entrada.refresh_from_db()
        except NFeEntradaPrepararProducaoError as exc:
            raise NFeEntradaEmissaoProducaoError(str(exc), detalhes={'erros': [str(exc)]}) from exc
    elif not nf_entrada.numero_nfe:
        NFeEntrada.objects.filter(pk=nf_entrada.pk).update(
            ambiente_emissao=NFeEntrada.AmbienteEmissao.PRODUCAO,
        )
        nf_entrada.refresh_from_db()

    try:
        exigir_pronta_ou_erro(validar_pre_emissao_producao_entrada(nf_entrada, exigir_numeracao=False))
    except NFeEntradaEmissaoValidationError as exc:
        raise NFeEntradaEmissaoProducaoError(str(exc), detalhes={'erros': [str(exc)]}) from exc

    if not nf_entrada.empresa_emitente_id:
        raise NFeEntradaEmissaoProducaoError('Empresa emitente obrigatória.')

    try:
        with transaction.atomic():
            nf = _lock_nfe_entrada(nf_entrada.pk)
            if nf.status_emissao_sefaz == NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
                raise NFeEntradaEmissaoProducaoError('NF-e já autorizada em produção SEFAZ.')
            if nf.status_emissao_sefaz == NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
                raise NFeEntradaEmissaoProducaoError(
                    'NF-e já autorizada em homologação — use nova NF-e para produção.',
                )
            if nf.numero_nfe and nf.ambiente_emissao != NFeEntrada.AmbienteEmissao.PRODUCAO:
                raise NFeEntradaEmissaoProducaoError(
                    'Numeração já reservada em outro ambiente — use "Preparar para produção".',
                )

            nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.PRODUCAO
            nf.save(update_fields=['ambiente_emissao'])

            if not (nf.numero_nfe and nf.serie_nfe and nf.chave_acesso):
                reservar_numeracao_nfe_entrada(nf, usuario=usuario)
                nf.refresh_from_db()

            empresa = nf.empresa_emitente
            _gerar_assinar_validar_xml_producao(nf, empresa, usuario=usuario)

    except NFeEntradaEmissaoProducaoError:
        raise
    except (NFeEntradaXmlError, NFeAssinaturaError) as exc:
        raise NFeEntradaEmissaoProducaoError(str(exc), detalhes={'erros': [str(exc)]}) from exc

    nf = NFeEntrada.objects.get(pk=nf_entrada.pk)
    empresa = nf.empresa_emitente

    try:
        resultado = transmitir_nfe_producao(nf, nf.xml_assinado, empresa)  # type: ignore[arg-type]
    except NFeTransmissaoProducaoError as exc:
        etapa = getattr(exc, 'etapa', 'TRANSMISSAO_SEFAZ_PRODUCAO') or 'TRANSMISSAO_SEFAZ_PRODUCAO'
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
        raise NFeEntradaEmissaoProducaoError(
            'Falha técnica ao transmitir NF-e entrada em produção.',
            detalhes={'erros': [str(exc)], 'etapa': etapa},
            etapa=etapa,
        ) from exc

    with transaction.atomic():
        nf = _lock_nfe_entrada(nf.pk)
        nf = aplicar_resultado_sefaz_producao_entrada(
            nf,
            resultado,
            empresa=empresa,
            usuario=usuario,
            xml_envio=nf.xml_envio_lote or nf.xml_assinado or '',
        )

    nf.refresh_from_db()
    logger.info(
        'EMISSAO_ENTRADA_PRODUCAO_FIM nf_id=%s autorizado=%s cStat=%s',
        nf.pk,
        resultado.autorizado,
        nf.cstat_autorizacao,
    )
    return montar_resposta_emissao_entrada(
        nf,
        ok=resultado.autorizado or resultado.rejeitado,
        ambiente='producao',
        autorizado=resultado.autorizado,
        mensagem=mensagem_resposta_resultado_entrada(resultado),
        resultado=resultado,
    )
