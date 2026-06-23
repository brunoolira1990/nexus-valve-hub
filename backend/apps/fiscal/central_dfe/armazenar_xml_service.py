"""Armazenamento manual de XML na Base DF-e Importada — Central DF-e."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.cadastros.models import Empresa
from apps.fiscal.central_dfe.service import (
    TIPO_CTE,
    TIPO_NFE_ENTRADA,
    ROTAS_DETALHE,
    _chaves_nfe_entrada_lancadas,
    _xml_conteudo_armazenado,
    documento_central_nfe_historica,
)
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

MSG_XML_NAO_PERSISTIDO = 'XML não foi persistido na Base NF-e Entrada Importada.'
MSG_CHAVE_INVALIDA = 'Chave de acesso inválida (44 dígitos).'
MSG_DOCUMENTO_NAO_ENCONTRADO = 'Documento NF-e não encontrado na Central DF-e.'
MSG_ID_CHAVE_DIVERGENTE = 'O identificador informado não corresponde à chave de acesso.'


class ArmazenarXmlCentralError(ValueError):
    pass


@dataclass
class _ContextoArmazenamentoNfe:
    chave: str
    nf: NFeEntradaHistoricaImportada | None = None
    manifestacao: NFeDestinadaManifestacao | None = None


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


def _normalizar_chave(chave: str | None) -> str:
    return ''.join(c for c in str(chave or '') if c.isdigit())


def _nf_historica_com_xml_or_raise(nf_id: int | None) -> NFeEntradaHistoricaImportada:
    if not nf_id:
        raise ArmazenarXmlCentralError(MSG_XML_NAO_PERSISTIDO)
    nf = (
        NFeEntradaHistoricaImportada.objects.select_related(
            'fornecedor_emitente',
            'empresa_destinataria',
            'conferencia',
        )
        .filter(pk=nf_id)
        .first()
    )
    if nf is None or not _xml_conteudo_armazenado(nf):
        raise ArmazenarXmlCentralError(MSG_XML_NAO_PERSISTIDO)
    return nf


def _validar_chave_documento(chave: str, registro_chave: str | None) -> None:
    if _normalizar_chave(registro_chave) != chave:
        raise ArmazenarXmlCentralError(MSG_ID_CHAVE_DIVERGENTE)


def _resolver_contexto_nfe_central(
    empresa: Empresa,
    *,
    documento_id: int | None,
    chave_acesso: str | None,
) -> _ContextoArmazenamentoNfe:
    """Resolve NF histórica e manifestação pela chave (fonte primária) e pelo id visual."""
    chave = _normalizar_chave(chave_acesso)
    nf: NFeEntradaHistoricaImportada | None = None
    manifestacao: NFeDestinadaManifestacao | None = None

    if len(chave) == 44:
        nf = (
            NFeEntradaHistoricaImportada.objects.select_related(
                'fornecedor_emitente',
                'empresa_destinataria',
                'conferencia',
            )
            .filter(empresa_destinataria=empresa, chave_acesso=chave)
            .first()
        )
        manifestacao = (
            NFeDestinadaManifestacao.objects.filter(empresa=empresa, chave_acesso=chave)
            .select_related('nf_entrada_historica')
            .first()
        )

    if documento_id:
        nf_por_id = (
            NFeEntradaHistoricaImportada.objects.select_related(
                'fornecedor_emitente',
                'empresa_destinataria',
                'conferencia',
            )
            .filter(pk=documento_id, empresa_destinataria=empresa)
            .first()
        )
        manifestacao_por_id = (
            NFeDestinadaManifestacao.objects.filter(pk=documento_id, empresa=empresa)
            .select_related('nf_entrada_historica')
            .first()
        )

        if nf_por_id and manifestacao_por_id:
            _validar_chave_documento(
                _normalizar_chave(nf_por_id.chave_acesso),
                manifestacao_por_id.chave_acesso,
            )

        if nf_por_id:
            if chave:
                _validar_chave_documento(chave, nf_por_id.chave_acesso)
            else:
                chave = _normalizar_chave(nf_por_id.chave_acesso)
            nf = nf_por_id
        elif manifestacao_por_id:
            if chave:
                _validar_chave_documento(chave, manifestacao_por_id.chave_acesso)
            else:
                chave = _normalizar_chave(manifestacao_por_id.chave_acesso)
            manifestacao = manifestacao_por_id

    if len(chave) != 44:
        raise ArmazenarXmlCentralError(MSG_CHAVE_INVALIDA)

    if nf is None and manifestacao and manifestacao.nf_entrada_historica_id:
        nf = manifestacao.nf_entrada_historica
    if nf is None and manifestacao is None:
        raise ArmazenarXmlCentralError(MSG_DOCUMENTO_NAO_ENCONTRADO)

    return _ContextoArmazenamentoNfe(chave=chave, nf=nf, manifestacao=manifestacao)


def _download_xml_url_nf(nf_id: int) -> str:
    return f'nf-entradas-historicas-importadas/{nf_id}/download-xml/'


def _resposta_armazenamento_nfe(
    *,
    empresa: Empresa,
    nf: NFeEntradaHistoricaImportada,
    manifestacao_id: int | None,
    duplicado: bool,
    mensagem: str,
) -> dict[str, Any]:
    documento = documento_central_nfe_historica(nf, empresa, _chaves_nfe_entrada_lancadas())
    if documento is None or not documento.xml_armazenado:
        raise ArmazenarXmlCentralError(MSG_XML_NAO_PERSISTIDO)
    documento_dict = documento.to_dict()
    return {
        'tipo_documento': TIPO_NFE_ENTRADA,
        'chave_acesso': (nf.chave_acesso or '').strip(),
        'xml_armazenado': True,
        'xml_status': XML_STATUS_ARMAZENADO,
        'nf_entrada_historica_id': nf.pk,
        'manifestacao_id': manifestacao_id,
        'duplicado': duplicado,
        'mensagem': mensagem,
        'detalhe_rota': documento_dict.get('detalhe_rota') or ROTAS_DETALHE[TIPO_NFE_ENTRADA],
        'download_xml_url': _download_xml_url_nf(nf.pk),
        'documento': documento_dict,
    }


def _manifestacao_para_download(
    *,
    empresa: Empresa,
    ctx: _ContextoArmazenamentoNfe,
    usuario=None,
) -> NFeDestinadaManifestacao:
    if ctx.manifestacao is not None:
        return ctx.manifestacao

    try:
        manifestacao, _ = iniciar_manifestacao_por_chave(
            empresa_id=empresa.pk,
            chave_acesso=ctx.chave,
            nf_entrada_historica_id=ctx.nf.pk if ctx.nf else None,
            usuario=usuario,
        )
    except IniciarPorChaveError as exc:
        raise ArmazenarXmlCentralError(str(exc)) from exc
    return manifestacao


@transaction.atomic
def armazenar_xml_nfe_central(
    *,
    empresa_id: int,
    documento_id: int | None = None,
    chave_acesso: str | None = None,
    usuario=None,
    confirmacao_explicita: bool = False,
) -> dict[str, Any]:
    """Armazena/confirma XML NF-e na Base NF-e Entrada Importada — ação manual explícita."""
    if not confirmacao_explicita:
        raise ArmazenarXmlCentralError('Confirmação explícita obrigatória para armazenar XML.')

    empresa = _empresa_or_raise(empresa_id)
    if documento_id is None and not (chave_acesso or '').strip():
        raise ArmazenarXmlCentralError(MSG_CHAVE_INVALIDA)

    ctx = _resolver_contexto_nfe_central(
        empresa,
        documento_id=documento_id,
        chave_acesso=chave_acesso,
    )

    if ctx.nf and eh_documento_homologacao(ctx.nf):
        raise ArmazenarXmlCentralError('NF-e de homologação não é armazenada como base fiscal oficial.')

    if ctx.nf and _xml_conteudo_armazenado(ctx.nf):
        manifestacao = sincronizar_manifestacao_com_nf_historica(ctx.nf, usuario=usuario)
        if manifestacao is None:
            raise ArmazenarXmlCentralError('NF-e sem empresa destinataria vinculada.')
        nf = _nf_historica_com_xml_or_raise(ctx.nf.pk)
        return _resposta_armazenamento_nfe(
            empresa=empresa,
            nf=nf,
            manifestacao_id=manifestacao.pk,
            duplicado=True,
            mensagem='XML já armazenado na Base NF-e Entrada Importada.',
        )

    manifestacao = _manifestacao_para_download(empresa=empresa, ctx=ctx, usuario=usuario)

    if (
        manifestacao.status_xml == NFeDestinadaManifestacao.StatusXml.BAIXADO
        and manifestacao.nf_entrada_historica_id
    ):
        try:
            nf = _nf_historica_com_xml_or_raise(manifestacao.nf_entrada_historica_id)
        except ArmazenarXmlCentralError:
            pass
        else:
            return _resposta_armazenamento_nfe(
                empresa=empresa,
                nf=nf,
                manifestacao_id=manifestacao.pk,
                duplicado=True,
                mensagem='XML já armazenado na Base NF-e Entrada Importada.',
            )

    try:
        if manifestacao.nf_entrada_historica_id is None:
            iniciar_manifestacao_por_chave(
                empresa_id=empresa_id,
                chave_acesso=ctx.chave,
                nf_entrada_historica_id=ctx.nf.pk if ctx.nf else None,
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
    nf_id = resultado.get('nf_entrada_historica_id') or manifestacao.nf_entrada_historica_id
    nf = _nf_historica_com_xml_or_raise(nf_id)
    if _normalizar_chave(nf.chave_acesso) != ctx.chave:
        raise ArmazenarXmlCentralError(MSG_ID_CHAVE_DIVERGENTE)

    return _resposta_armazenamento_nfe(
        empresa=empresa,
        nf=nf,
        manifestacao_id=manifestacao.pk,
        duplicado=bool(resultado.get('duplicado')),
        mensagem='XML armazenado na Base NF-e Entrada Importada.',
    )


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
