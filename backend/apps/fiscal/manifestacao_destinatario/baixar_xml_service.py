"""Download manual de XML completo e classificação como Base DF-e Importada."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.dfe_recebidos.distribuicao_dfe_parser import parse_distribuicao_dfe_response
from apps.fiscal.manifestacao_destinatario.audit import registrar_evento_manifestacao
from apps.fiscal.models import (
    NFeDestinadaManifestacao,
    NFeDestinadaManifestacaoEvento,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.nfe_historica_classificacao import norm_digits
from apps.fiscal.nfe_import.service_entrada import importar_arquivos_entrada
from apps.fiscal.xml_armazenamento import ORIGEM_MANIFESTACAO_DOWNLOAD, persistir_xml_nfe_entrada
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    consulta_distribuicao_dfe_nfe_por_chave,
    criar_comunicacao_sefaz,
)

logger = logging.getLogger(__name__)

MSG_CERTIFICADO = 'Certificado digital não disponível/configurado para download XML.'
MSG_XML_INDISPONIVEL = 'XML completo ainda não disponível na SEFAZ para esta NF-e.'
MSG_CHAVE_INVALIDA = 'Chave de acesso inválida.'
MSG_CNPJ_DEST = 'CNPJ destinatário do XML não corresponde à empresa.'


class BaixarXmlDestinatarioError(ValueError):
    pass


def _extrair_xml_nfe(parsed_docs) -> bytes | None:
    for doc in parsed_docs:
        if doc.tipo == 'NFE' and doc.conteudo_xml:
            return doc.conteudo_xml
    return None


def _validar_destinatario_xml(xml_bytes: bytes, cnpj_esperado: str) -> None:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise BaixarXmlDestinatarioError('XML retornado pela SEFAZ é inválido.') from exc

    dest_cnpj = ''
    tp_amb = ''
    for el in root.iter():
        tag = el.tag.split('}')[-1]
        if tag == 'dest':
            for child in el:
                if child.tag.split('}')[-1] in {'CNPJ', 'CPF'}:
                    dest_cnpj = norm_digits(child.text or '')
        if tag == 'tpAmb' and not tp_amb:
            tp_amb = (el.text or '').strip()

    if tp_amb and tp_amb != '1':
        raise BaixarXmlDestinatarioError('XML de homologação não é importado como base fiscal oficial.')
    if dest_cnpj != cnpj_esperado:
        raise BaixarXmlDestinatarioError(MSG_CNPJ_DEST)


@transaction.atomic
def baixar_xml_documento_destinatario(
    documento: NFeDestinadaManifestacao,
    *,
    confirmacao_explicita: bool = False,
    usuario=None,
    consulta_fn=None,
) -> dict[str, Any]:
    if not confirmacao_explicita:
        raise BaixarXmlDestinatarioError('Confirmação explícita obrigatória para baixar XML.')

    documento = NFeDestinadaManifestacao.objects.select_for_update().select_related('empresa').get(
        pk=documento.pk,
    )

    if documento.status_xml == NFeDestinadaManifestacao.StatusXml.BAIXADO and documento.nf_entrada_historica_id:
        nf_existente = NFeEntradaHistoricaImportada.objects.filter(
            pk=documento.nf_entrada_historica_id,
        ).first()
        if nf_existente and (nf_existente.xml_conteudo or '').strip():
            return {
                'documento_id': documento.pk,
                'status_xml': documento.status_xml,
                'nf_entrada_historica_id': documento.nf_entrada_historica_id,
                'mensagem': 'XML já baixado anteriormente.',
            }

    chave = (documento.chave_acesso or '').strip()
    if len(chave) != 44:
        raise BaixarXmlDestinatarioError(MSG_CHAVE_INVALIDA)

    empresa = documento.empresa
    cnpj = norm_digits(empresa.cnpj)
    if len(cnpj) != 14:
        raise BaixarXmlDestinatarioError('CNPJ da empresa inválido.')

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise BaixarXmlDestinatarioError(MSG_CERTIFICADO) from exc
    if not cert_info.valido:
        raise BaixarXmlDestinatarioError(MSG_CERTIFICADO)

    uf = (empresa.uf or 'SP').strip().upper()
    senha = (empresa.senha_certificado or '').strip()

    if consulta_fn is None:
        comm = criar_comunicacao_sefaz(uf, cert_info.caminho, senha, homologacao=False)
        consulta_fn = lambda: consulta_distribuicao_dfe_nfe_por_chave(comm, cnpj, chave)

    try:
        resposta = consulta_fn()
    except PyNFeComunicacaoError as exc:
        documento.status_xml = NFeDestinadaManifestacao.StatusXml.ERRO
        documento.ultimo_xmotivo = str(exc)[:255]
        documento.save(update_fields=['status_xml', 'ultimo_xmotivo', 'consultado_em'])
        registrar_evento_manifestacao(
            documento,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.BAIXA_XML,
            descricao='Tentativa de download XML via distribuição DF-e.',
            usuario=usuario,
            resultado_resumido='Erro SEFAZ',
            xmotivo=str(exc)[:255],
        )
        raise BaixarXmlDestinatarioError(str(exc)) from exc

    parsed = parse_distribuicao_dfe_response(resposta)
    xml_bytes = _extrair_xml_nfe(parsed.documentos)
    if not xml_bytes:
        raise BaixarXmlDestinatarioError(MSG_XML_INDISPONIVEL)

    _validar_destinatario_xml(xml_bytes, cnpj)

    nome = f'manifestacao_dest_{chave}.xml'
    resultado = importar_arquivos_entrada([(nome, xml_bytes)])

    if resultado.get('erros'):
        msg = resultado['erros'][0].get('mensagem_completa') or resultado['erros'][0].get('mensagem')
        raise BaixarXmlDestinatarioError(str(msg))

    nf_hist_id = None
    if resultado.get('importadas'):
        nf_hist_id = resultado['importadas'][0].get('id')
    elif resultado.get('duplicadas'):
        dup = NFeEntradaHistoricaImportada.objects.filter(chave_acesso=chave).first()
        nf_hist_id = dup.pk if dup else None

    if nf_hist_id:
        nf_hist = NFeEntradaHistoricaImportada.objects.filter(pk=nf_hist_id).first()
        if nf_hist:
            gravou = persistir_xml_nfe_entrada(
                nf_hist,
                xml_bytes,
                origem=ORIGEM_MANIFESTACAO_DOWNLOAD,
                nome_arquivo=nome,
                forcar=True,
            )
            if not gravou:
                raise BaixarXmlDestinatarioError(
                    'Não foi possível gravar o XML na Base NF-e Entrada Importada.',
                )
            nf_hist.refresh_from_db()
            if not (nf_hist.xml_conteudo or '').strip():
                raise BaixarXmlDestinatarioError(
                    'XML não foi persistido na Base NF-e Entrada Importada.',
                )
    else:
        raise BaixarXmlDestinatarioError('NF-e não foi vinculada na Base NF-e Entrada Importada.')

    agora = timezone.now()
    documento.status_xml = NFeDestinadaManifestacao.StatusXml.BAIXADO
    documento.xml_baixado_em = agora
    documento.classificacao_dfe = 'BASE_DFE_IMPORTADA'
    if nf_hist_id:
        documento.nf_entrada_historica_id = nf_hist_id
    documento.save(
        update_fields=[
            'status_xml',
            'xml_baixado_em',
            'classificacao_dfe',
            'nf_entrada_historica',
            'consultado_em',
        ],
    )

    evt = registrar_evento_manifestacao(
        documento,
        tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.BAIXA_XML,
        descricao='XML completo baixado e classificado como Base DF-e Importada.',
        usuario=usuario,
        resultado_resumido='XML baixado',
        cstat=parsed.cstat,
        xmotivo=parsed.xmotivo,
        dados_json={
            'nf_entrada_historica_id': nf_hist_id,
            'classificacao_dfe': 'BASE_DFE_IMPORTADA',
        },
    )

    logger.info(
        'XML destinada baixado doc=%s chave=%s nf_hist=%s',
        documento.pk,
        chave[:8] + '...',
        nf_hist_id,
    )

    return {
        'documento_id': documento.pk,
        'status_xml': documento.status_xml,
        'nf_entrada_historica_id': nf_hist_id,
        'classificacao_dfe': documento.classificacao_dfe,
        'evento_id': evt.pk,
        'duplicado': bool(resultado.get('duplicadas')),
    }
