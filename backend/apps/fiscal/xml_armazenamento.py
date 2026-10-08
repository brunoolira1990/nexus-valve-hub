"""Persistência do XML completo importado — NF-e e CT-e (exportação posterior)."""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.manifestacao_destinatario.audit import registrar_evento_manifestacao
from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeDestinadaManifestacao,
    NFeDestinadaManifestacaoEvento,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.central_dfe.service import _xml_conteudo_armazenado
from apps.fiscal.nfe_historica_classificacao import norm_digits

logger = logging.getLogger(__name__)

ORIGEM_CENTRAL_DFE = 'CENTRAL_DFE'
ORIGEM_MANIFESTACAO_DOWNLOAD = 'MANIFESTACAO_DOWNLOAD'
ORIGEM_IMPORTACAO_MANUAL = 'IMPORTACAO_MANUAL'
ORIGEM_DISTRIBUICAO_DFE = 'DISTRIBUICAO_DFE'
ORIGEM_CAPTURA_SEFAZ = 'CAPTURA_SEFAZ'


def normalizar_xml_texto(conteudo: bytes | str) -> str:
    if isinstance(conteudo, bytes):
        for encoding in ('utf-8', 'latin-1'):
            try:
                texto = conteudo.decode(encoding)
                if texto.strip():
                    return texto
            except UnicodeDecodeError:
                continue
        return conteudo.decode('utf-8', errors='replace')
    return (conteudo or '').strip()


def _merge_meta_xml(prot_json: dict[str, Any] | None, *, origem: str) -> dict[str, Any]:
    meta = dict(prot_json or {})
    nexus = dict(meta.get('_nexus') or {})
    nexus['origem_xml'] = origem
    nexus['xml_armazenado_em'] = timezone.now().isoformat()
    meta['_nexus'] = nexus
    return meta


def persistir_xml_nfe_entrada(
    nf: NFeEntradaHistoricaImportada,
    conteudo: bytes | str,
    *,
    origem: str,
    nome_arquivo: str = '',
    forcar: bool = False,
) -> bool:
    """Grava XML completo no registro NF-e. Retorna True se gravou/atualizou."""
    xml_texto = normalizar_xml_texto(conteudo)
    if not xml_texto:
        return False
    if nf.xml_conteudo and not forcar:
        return False
    update_fields = ['xml_conteudo', 'prot_json']
    nf.xml_conteudo = xml_texto
    nf.prot_json = _merge_meta_xml(nf.prot_json, origem=origem)
    if nome_arquivo and not nf.nome_arquivo:
        nf.nome_arquivo = nome_arquivo[:255]
        update_fields.append('nome_arquivo')
    nf.save(update_fields=update_fields)
    logger.info(
        'XML NF-e armazenado id=%s chave=%s origem=%s',
        nf.pk,
        (nf.chave_acesso or '')[:8] + '...',
        origem,
    )
    return True


def persistir_xml_cte(
    cte: CTeHistoricoImportado,
    conteudo: bytes | str,
    *,
    origem: str,
    nome_arquivo: str = '',
    forcar: bool = False,
) -> bool:
    xml_texto = normalizar_xml_texto(conteudo)
    if not xml_texto:
        return False
    if cte.xml_conteudo and not forcar:
        return False
    update_fields = ['xml_conteudo', 'prot_json']
    cte.xml_conteudo = xml_texto
    cte.prot_json = _merge_meta_xml(cte.prot_json, origem=origem)
    if nome_arquivo and not cte.nome_arquivo:
        cte.nome_arquivo = nome_arquivo[:255]
        update_fields.append('nome_arquivo')
    cte.save(update_fields=update_fields)
    logger.info(
        'XML CT-e armazenado id=%s chave=%s origem=%s',
        cte.pk,
        (cte.chave_acesso or '')[:8] + '...',
        origem,
    )
    return True


def sincronizar_manifestacao_com_nf_historica(
    nf: NFeEntradaHistoricaImportada,
    *,
    usuario=None,
) -> NFeDestinadaManifestacao | None:
    """Vincula/atualiza manifestação quando NF-e já está na base importada."""
    empresa = nf.empresa_destinataria
    if empresa is None:
        return None

    cnpj_dest = norm_digits(empresa.cnpj)
    emit_nome = ''
    emit_cnpj = ''
    if nf.fornecedor_emitente_id and nf.fornecedor_emitente:
        emit_nome = nf.fornecedor_emitente.razao_social or ''
        emit_cnpj = norm_digits(nf.fornecedor_emitente.cnpj)
    elif nf.emit_json:
        emit_nome = (nf.emit_json.get('xNome') or nf.emit_json.get('xFant') or '').strip()
        emit_cnpj = norm_digits(str(nf.emit_json.get('CNPJ') or nf.emit_json.get('CPF') or ''))

    tp_amb = (nf.tp_amb or '1').strip()
    ambiente = (
        NFeDestinadaManifestacao.Ambiente.PRODUCAO
        if tp_amb == '1'
        else NFeDestinadaManifestacao.Ambiente.HOMOLOGACAO
    )

    documento, created = NFeDestinadaManifestacao.objects.update_or_create(
        empresa=empresa,
        chave_acesso=nf.chave_acesso,
        defaults={
            'cnpj_destinatario': cnpj_dest,
            'cnpj_emitente': emit_cnpj,
            'razao_social_emitente': (emit_nome or '')[:255],
            'dh_emissao': nf.dh_emissao,
            'valor_nf': nf.valor_total_nf,
            'ambiente': ambiente,
            'classificacao_dfe': 'BASE_DFE_IMPORTADA',
            'nf_entrada_historica': nf,
        },
    )
    xml_armazenado = _xml_conteudo_armazenado(nf)
    if created:
        documento.status_xml = (
            NFeDestinadaManifestacao.StatusXml.BAIXADO
            if xml_armazenado
            else NFeDestinadaManifestacao.StatusXml.RESUMO
        )
        documento.save(update_fields=['status_xml', 'consultado_em'])
        registrar_evento_manifestacao(
            documento=documento,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.CONSULTA,
            descricao='Registro de manifestação vinculado à NF-e armazenada na Base NF-e Entrada Importada.',
            usuario=usuario,
            ambiente=ambiente,
        )
    else:
        update_fields = ['nf_entrada_historica', 'consultado_em']
        documento.nf_entrada_historica = nf
        if xml_armazenado and documento.status_xml != NFeDestinadaManifestacao.StatusXml.BAIXADO:
            documento.status_xml = NFeDestinadaManifestacao.StatusXml.BAIXADO
            update_fields.append('status_xml')
        documento.save(update_fields=update_fields)
    return documento


def xml_nfe_disponivel_local(chave_acesso: str) -> NFeEntradaHistoricaImportada | None:
    chave = (chave_acesso or '').strip()
    if len(chave) != 44:
        return None
    return NFeEntradaHistoricaImportada.objects.filter(chave_acesso=chave).first()


def xml_cte_disponivel_local(chave_acesso: str) -> CTeHistoricoImportado | None:
    chave = (chave_acesso or '').strip()
    if len(chave) != 44:
        return None
    return CTeHistoricoImportado.objects.filter(chave_acesso=chave).first()
