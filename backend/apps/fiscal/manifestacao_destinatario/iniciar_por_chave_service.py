"""Prepara registro de manifestação por chave — sem evento fiscal e sem download XML."""

from __future__ import annotations

from django.db import transaction

from apps.cadastros.models import Empresa
from apps.fiscal.central_dfe.service import _json_participante, _xml_conteudo_armazenado, normalizar_cnpj
from apps.fiscal.dfe_classificacao import eh_documento_homologacao
from apps.fiscal.manifestacao_destinatario.audit import registrar_evento_manifestacao
from apps.fiscal.models import NFeDestinadaManifestacao, NFeDestinadaManifestacaoEvento, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_historica_classificacao import norm_digits


class IniciarPorChaveError(ValueError):
    pass


def _emitente_nf(nf: NFeEntradaHistoricaImportada) -> tuple[str, str]:
    if nf.fornecedor_emitente_id and nf.fornecedor_emitente:
        return nf.fornecedor_emitente.razao_social or '', normalizar_cnpj(nf.fornecedor_emitente.cnpj)
    return _json_participante(nf.emit_json)


@transaction.atomic
def iniciar_manifestacao_por_chave(
    *,
    empresa_id: int,
    chave_acesso: str,
    nf_entrada_historica_id: int | None = None,
    usuario=None,
) -> tuple[NFeDestinadaManifestacao, bool]:
    """Localiza ou cria NFeDestinadaManifestacao a partir de NF-e recebida/importada.

    Não consulta SEFAZ, não envia manifestação e não baixa XML.
    """
    chave = ''.join(c for c in str(chave_acesso or '') if c.isdigit())
    if len(chave) != 44:
        raise IniciarPorChaveError('Chave de acesso inválida (44 dígitos).')

    try:
        empresa = Empresa.objects.get(pk=empresa_id)
    except Empresa.DoesNotExist as exc:
        raise IniciarPorChaveError('Empresa não encontrada.') from exc

    cnpj_dest = norm_digits(empresa.cnpj)
    if len(cnpj_dest) != 14:
        raise IniciarPorChaveError('CNPJ da empresa inválido.')

    existente = NFeDestinadaManifestacao.objects.select_for_update().filter(
        empresa=empresa,
        chave_acesso=chave,
    ).first()
    if existente:
        if nf_entrada_historica_id and not existente.nf_entrada_historica_id:
            nf_link = NFeEntradaHistoricaImportada.objects.filter(
                pk=nf_entrada_historica_id,
                empresa_destinataria=empresa,
                chave_acesso=chave,
            ).first()
            if nf_link:
                existente.nf_entrada_historica = nf_link
                if _xml_conteudo_armazenado(nf_link):
                    existente.status_xml = NFeDestinadaManifestacao.StatusXml.BAIXADO
                elif existente.status_xml == NFeDestinadaManifestacao.StatusXml.PENDENTE:
                    existente.status_xml = NFeDestinadaManifestacao.StatusXml.RESUMO
                existente.save(update_fields=['nf_entrada_historica', 'status_xml', 'consultado_em'])
        return existente, False

    nf: NFeEntradaHistoricaImportada | None = None
    if nf_entrada_historica_id:
        nf = NFeEntradaHistoricaImportada.objects.filter(
            pk=nf_entrada_historica_id,
            empresa_destinataria=empresa,
        ).first()
        if nf and norm_digits(nf.chave_acesso) != chave:
            raise IniciarPorChaveError('Identificador do DF-e não corresponde à chave informada.')
    if nf is None:
        nf = NFeEntradaHistoricaImportada.objects.filter(
            chave_acesso=chave,
            empresa_destinataria=empresa,
        ).first()
    if nf is None:
        raise IniciarPorChaveError(
            'NF-e recebida não encontrada para esta chave e empresa. '
            'Atualize a Central DF-e ou importe o documento antes de manifestar.',
        )
    if eh_documento_homologacao(nf):
        raise IniciarPorChaveError('NF-e de homologação não aplicável à manifestação do destinatário.')

    tp_amb = (nf.tp_amb or '1').strip()
    ambiente = (
        NFeDestinadaManifestacao.Ambiente.PRODUCAO
        if tp_amb == '1'
        else NFeDestinadaManifestacao.Ambiente.HOMOLOGACAO
    )
    emit_nome, emit_cnpj = _emitente_nf(nf)

    status_xml_inicial = (
        NFeDestinadaManifestacao.StatusXml.BAIXADO
        if _xml_conteudo_armazenado(nf)
        else NFeDestinadaManifestacao.StatusXml.RESUMO
    )
    documento = NFeDestinadaManifestacao.objects.create(
        empresa=empresa,
        chave_acesso=chave,
        cnpj_destinatario=cnpj_dest,
        cnpj_emitente=norm_digits(emit_cnpj),
        razao_social_emitente=(emit_nome or '')[:255],
        dh_emissao=nf.dh_emissao,
        valor_nf=nf.valor_total_nf,
        ambiente=ambiente,
        classificacao_dfe='BASE_DFE_IMPORTADA',
        status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.PENDENTE,
        status_xml=status_xml_inicial,
        nf_entrada_historica=nf,
    )

    registrar_evento_manifestacao(
        documento=documento,
        tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.CONSULTA,
        descricao='Registro preparado para manifestação manual (Central DF-e).',
        usuario=usuario,
        ambiente=ambiente,
    )

    return documento, True
