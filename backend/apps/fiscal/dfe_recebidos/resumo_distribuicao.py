"""Persistência de resumos NF-e (resNFe) retornados na distribuição DF-e SEFAZ."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from apps.cadastros.models import Empresa
from apps.fiscal.dfe_recebidos.distribuicao_dfe_parser import DocumentoDistribuicao
from apps.fiscal.manifestacao_destinatario.resnfe_parser import parse_resnfe_xml
from apps.fiscal.models import NFeDestinadaManifestacao
from apps.fiscal.nfe_historica_classificacao import norm_digits

logger = logging.getLogger(__name__)


def upsert_resnfe_destinada(
    *,
    empresa: Empresa,
    cnpj_dest: str,
    nsu: str,
    parsed,
) -> tuple[NFeDestinadaManifestacao | None, bool]:
    if parsed.tp_amb != '1':
        return None, False

    obj, created = NFeDestinadaManifestacao.objects.update_or_create(
        empresa=empresa,
        chave_acesso=parsed.chave_acesso,
        defaults={
            'nsu': nsu,
            'cnpj_destinatario': cnpj_dest,
            'cnpj_emitente': parsed.cnpj_emitente,
            'razao_social_emitente': parsed.razao_social_emitente,
            'ie_emitente': parsed.ie_emitente,
            'dh_emissao': parsed.dh_emissao,
            'valor_nf': parsed.valor_nf,
            'ambiente': NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            'classificacao_dfe': 'BASE_DFE_IMPORTADA',
            'resumo_json': parsed.resumo_json,
            'status_xml': NFeDestinadaManifestacao.StatusXml.RESUMO,
        },
    )
    if not created and obj.status_xml == NFeDestinadaManifestacao.StatusXml.PENDENTE:
        obj.status_xml = NFeDestinadaManifestacao.StatusXml.RESUMO
        obj.save(update_fields=['status_xml', 'consultado_em'])
    return obj, created


def marcar_xml_nfe_disponivel_destinada(
    *,
    empresa: Empresa,
    cnpj_dest: str,
    nsu: str,
    chave: str,
) -> NFeDestinadaManifestacao | None:
    obj = NFeDestinadaManifestacao.objects.filter(empresa=empresa, chave_acesso=chave).first()
    if obj is None:
        return NFeDestinadaManifestacao.objects.create(
            empresa=empresa,
            chave_acesso=chave,
            nsu=nsu,
            cnpj_destinatario=cnpj_dest,
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            classificacao_dfe='BASE_DFE_IMPORTADA',
            status_xml=NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
        )
    if obj.status_xml not in (
        NFeDestinadaManifestacao.StatusXml.BAIXADO,
        NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
    ):
        obj.status_xml = NFeDestinadaManifestacao.StatusXml.DISPONIVEL
        obj.nsu = nsu or obj.nsu
        obj.save(update_fields=['status_xml', 'nsu', 'consultado_em'])
    return obj


def _extrair_chave_nfe_xml(conteudo_xml: bytes) -> str:
    try:
        root = ET.fromstring(conteudo_xml)
    except ET.ParseError:
        return ''
    for el in root.iter():
        if el.tag.split('}')[-1] == 'chNFe':
            chave = (el.text or '').strip()
            if len(chave) == 44:
                return chave
    return ''


def processar_documentos_resumo_nfe_distribuicao(
    *,
    empresa: Empresa,
    cnpj_dest: str,
    documentos: list[DocumentoDistribuicao],
) -> dict[str, int]:
    """Grava resNFe/XML disponível na base de manifestação — sem evento fiscal."""
    cnpj_norm = norm_digits(cnpj_dest)
    resumos = 0
    resumos_novos = 0
    resumos_atualizados = 0
    xml_disponivel = 0
    ignorados_homolog = 0

    for doc in documentos:
        if doc.tipo == 'RES_NFE':
            resumos += 1
            parsed_res = parse_resnfe_xml(doc.conteudo_xml)
            if not parsed_res:
                continue
            if parsed_res.tp_amb != '1':
                ignorados_homolog += 1
                continue
            _, created = upsert_resnfe_destinada(
                empresa=empresa,
                cnpj_dest=cnpj_norm,
                nsu=doc.nsu,
                parsed=parsed_res,
            )
            if created:
                resumos_novos += 1
            else:
                resumos_atualizados += 1
        elif doc.tipo == 'NFE':
            chave = _extrair_chave_nfe_xml(doc.conteudo_xml)
            if chave:
                obj = marcar_xml_nfe_disponivel_destinada(
                    empresa=empresa,
                    cnpj_dest=cnpj_norm,
                    nsu=doc.nsu,
                    chave=chave,
                )
                if obj:
                    xml_disponivel += 1

    return {
        'resumos': resumos,
        'resumos_novos': resumos_novos,
        'resumos_atualizados': resumos_atualizados,
        'xml_disponivel': xml_disponivel,
        'ignorados_homolog': ignorados_homolog,
    }
