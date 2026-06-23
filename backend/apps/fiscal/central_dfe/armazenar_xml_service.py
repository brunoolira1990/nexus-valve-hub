"""Armazenamento manual de XML na Base DF-e Importada — Central DF-e."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.cadastros.models import Empresa
from apps.fiscal.central_dfe.service import TIPO_CTE, TIPO_NFE_ENTRADA, normalizar_cnpj
from apps.fiscal.dfe_classificacao import eh_documento_homologacao
from apps.fiscal.manifestacao_destinatario.baixar_xml_service import (
    BaixarXmlDestinatarioError,
    baixar_xml_documento_destinatario,
)
from apps.fiscal.manifestacao_destinatario.iniciar_por_chave_service import (
    IniciarPorChaveError,
    iniciar_manifestacao_por_chave,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeDestinadaManifestacao,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.xml_armazenamento import sincronizar_manifestacao_com_nf_historica

logger = logging.getLogger(__name__)

XML_STATUS_ARMAZENADO = 'ARMAZENADO'
XML_STATUS_PENDENTE = 'PENDENTE'
XML_STATUS_DISPONIVEL = 'DISPONIVEL'
XML_STATUS_ERRO = 'ERRO'


class ArmazenarXmlCentralError(ValueError):
    pass


def _empresa_or_raise(empresa_id: int) -> Empresa:
    try:
        return Empresa.objects.get(pk=empresa_id)
    except Empresa.DoesNotExist as exc:
        raise ArmazenarXmlCentralError('Empresa não encontrada.') from exc


def _cte_pertence_empresa(cte: CTeHistoricoImportado, empresa: Empresa) -> bool:
    emp_id = empresa.pk
    return emp_id in {
        cte.empresa_tomadora_id,
        cte.empresa_destinataria_id,
        cte.empresa_recebedora_id,
    }


from apps.fiscal.xml_armazenamento import sincronizar_manifestacao_com_nf_historica


@transaction.atomic
def armazenar_xml_nfe_central(
    *,
    empresa_id: int,
    documento_id: int,
    usuario=None,
    confirmacao_explicita: bool = False,
) -> dict[str, Any]:
    """Armazena/confirma XML NF-e na Base NF-e Entrada Importada — ação manual explícita."""
    if not confirmacao_explicita:
        raise ArmazenarXmlCentralError('Confirmação explícita obrigatória para armazenar XML.')

    empresa = _empresa_or_raise(empresa_id)

    nf = NFeEntradaHistoricaImportada.objects.filter(
        pk=documento_id,
        empresa_destinataria=empresa,
    ).first()
    if nf is not None:
        if eh_documento_homologacao(nf):
            raise ArmazenarXmlCentralError('NF-e de homologação não é armazenada como base fiscal oficial.')
        documento = sincronizar_manifestacao_com_nf_historica(nf, usuario=usuario)
        if documento is None:
            raise ArmazenarXmlCentralError('NF-e sem empresa destinataria vinculada.')
        return {
            'tipo_documento': TIPO_NFE_ENTRADA,
            'xml_armazenado': True,
            'xml_status': XML_STATUS_ARMAZENADO,
            'nf_entrada_historica_id': nf.pk,
            'manifestacao_id': documento.pk,
            'duplicado': True,
            'mensagem': 'XML já armazenado na Base NF-e Entrada Importada.',
        }

    manifestacao = NFeDestinadaManifestacao.objects.filter(
        pk=documento_id,
        empresa=empresa,
    ).select_related('nf_entrada_historica').first()
    if manifestacao is None:
        raise ArmazenarXmlCentralError('Documento NF-e não encontrado na Central DF-e.')

    if manifestacao.status_xml == NFeDestinadaManifestacao.StatusXml.BAIXADO and manifestacao.nf_entrada_historica_id:
        return {
            'tipo_documento': TIPO_NFE_ENTRADA,
            'xml_armazenado': True,
            'xml_status': XML_STATUS_ARMAZENADO,
            'nf_entrada_historica_id': manifestacao.nf_entrada_historica_id,
            'manifestacao_id': manifestacao.pk,
            'duplicado': True,
            'mensagem': 'XML já armazenado na Base NF-e Entrada Importada.',
        }

    try:
        if manifestacao.nf_entrada_historica_id is None and len((manifestacao.chave_acesso or '').strip()) == 44:
            iniciar_manifestacao_por_chave(
                empresa_id=empresa_id,
                chave_acesso=manifestacao.chave_acesso,
                usuario=usuario,
            )
            manifestacao.refresh_from_db()
    except IniciarPorChaveError:
        pass

    try:
        resultado = baixar_xml_documento_destinatario(
            manifestacao,
            confirmacao_explicita=True,
            usuario=usuario,
        )
    except BaixarXmlDestinatarioError as exc:
        raise ArmazenarXmlCentralError(str(exc)) from exc

    manifestacao.refresh_from_db()
    return {
        'tipo_documento': TIPO_NFE_ENTRADA,
        'xml_armazenado': True,
        'xml_status': XML_STATUS_ARMAZENADO,
        'nf_entrada_historica_id': resultado.get('nf_entrada_historica_id'),
        'manifestacao_id': manifestacao.pk,
        'duplicado': bool(resultado.get('duplicado')),
        'mensagem': 'XML armazenado na Base NF-e Entrada Importada.',
    }


@transaction.atomic
def armazenar_xml_cte_central(
    *,
    empresa_id: int,
    documento_id: int,
    usuario=None,
    confirmacao_explicita: bool = False,
) -> dict[str, Any]:
    """Confirma/armazena XML CT-e na Base CT-e Importada — ação manual explícita."""
    if not confirmacao_explicita:
        raise ArmazenarXmlCentralError('Confirmação explícita obrigatória para armazenar XML.')

    empresa = _empresa_or_raise(empresa_id)
    cte = CTeHistoricoImportado.objects.filter(pk=documento_id).first()
    if cte is None or not _cte_pertence_empresa(cte, empresa):
        raise ArmazenarXmlCentralError('CT-e não encontrado na Central DF-e para a empresa informada.')

    if eh_documento_homologacao(cte):
        raise ArmazenarXmlCentralError('CT-e de homologação não é armazenado como base fiscal oficial.')

    logger.info(
        'XML CT-e confirmado na base importada cte=%s chave=%s',
        cte.pk,
        (cte.chave_acesso or '')[:8] + '...',
    )

    return {
        'tipo_documento': TIPO_CTE,
        'xml_armazenado': True,
        'xml_status': XML_STATUS_ARMAZENADO,
        'cte_historico_id': cte.pk,
        'duplicado': True,
        'mensagem': 'XML já armazenado na Base CT-e Importada.',
    }
