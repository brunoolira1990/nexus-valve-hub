"""Consulta de NF-e destinadas via distribuição DF-e SEFAZ.

Somente resgata resumos/documentos destinados (dist NSU). Não envia evento fiscal
de manifestação do destinatário e não baixa XML completo.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.dfe_recebidos.distribuicao_dfe_parser import parse_distribuicao_dfe_response
from apps.fiscal.dfe_recebidos.nsu_estado import carregar_estado_nsu, salvar_estado_nsu
from apps.fiscal.manifestacao_destinatario.audit import registrar_evento_manifestacao
from apps.fiscal.manifestacao_destinatario.resnfe_parser import parse_resnfe_xml
from apps.fiscal.models import NFeDestinadaManifestacao, NFeDestinadaManifestacaoEvento
from apps.fiscal.nfe_historica_classificacao import norm_digits
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    consulta_distribuicao_dfe_nfe,
    criar_comunicacao_sefaz,
)
from apps.fiscal.nfe_integracao.prontidao_consulta_sefaz import validar_prontidao_consulta_sefaz

logger = logging.getLogger(__name__)

TIPO_NFE = 'NFE'
MSG_CERTIFICADO = 'Certificado digital não disponível/configurado para consulta DF-e.'


class ManifestacaoConsultaError(ValueError):
    pass


def _upsert_resnfe(
    *,
    empresa: Empresa,
    cnpj_dest: str,
    nsu: str,
    parsed,
) -> tuple[NFeDestinadaManifestacao, bool]:
    if parsed.tp_amb != '1':
        return None, False  # type: ignore[return-value]

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


def _marcar_xml_disponivel(
    *,
    empresa: Empresa,
    cnpj_dest: str,
    nsu: str,
    chave: str,
) -> NFeDestinadaManifestacao | None:
    obj = NFeDestinadaManifestacao.objects.filter(empresa=empresa, chave_acesso=chave).first()
    if obj is None:
        obj = NFeDestinadaManifestacao.objects.create(
            empresa=empresa,
            chave_acesso=chave,
            nsu=nsu,
            cnpj_destinatario=cnpj_dest,
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            classificacao_dfe='BASE_DFE_IMPORTADA',
            status_xml=NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
        )
        return obj
    if obj.status_xml not in (
        NFeDestinadaManifestacao.StatusXml.BAIXADO,
        NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
    ):
        obj.status_xml = NFeDestinadaManifestacao.StatusXml.DISPONIVEL
        obj.nsu = nsu or obj.nsu
        obj.save(update_fields=['status_xml', 'nsu', 'consultado_em'])
    return obj


@transaction.atomic
def consultar_nfe_destinadas(
    *,
    empresa_id: int,
    usuario=None,
    limite_lotes: int = 3,
) -> dict[str, Any]:
    """Consulta resumos destinados na SEFAZ (dist NSU) sem manifestar nem baixar XML."""
    try:
        empresa = Empresa.objects.get(pk=empresa_id)
    except Empresa.DoesNotExist as exc:
        raise ManifestacaoConsultaError('Empresa não encontrada.') from exc

    cnpj_dest = norm_digits(empresa.cnpj)
    if len(cnpj_dest) != 14:
        raise ManifestacaoConsultaError('CNPJ da empresa inválido para consulta DF-e.')

    pode, motivo, _ = validar_prontidao_consulta_sefaz(empresa)
    if not pode:
        raise ManifestacaoConsultaError(motivo or MSG_CERTIFICADO)

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise ManifestacaoConsultaError(MSG_CERTIFICADO) from exc
    if not cert_info.valido:
        raise ManifestacaoConsultaError(MSG_CERTIFICADO)

    cert_cnpj = norm_digits(cert_info.cnpj or '')
    if cert_cnpj and cert_cnpj != cnpj_dest:
        raise ManifestacaoConsultaError(
            'CNPJ do certificado A1 não corresponde ao CNPJ da empresa ativa.',
        )

    uf = (empresa.uf or 'SP').strip().upper()
    senha = (empresa.senha_certificado or '').strip()
    limite = max(1, min(int(limite_lotes or 3), 20))

    comm = criar_comunicacao_sefaz(uf, cert_info.caminho, senha, homologacao=False)
    estado = carregar_estado_nsu(empresa.pk, TIPO_NFE)
    ult_nsu = estado.ultimo_nsu

    novos = 0
    atualizados = 0
    resumos = 0
    xml_disponivel = 0
    ignorados_homolog = 0
    mensagens: list[str] = []
    erros: list[str] = []
    lotes = 0

    for _ in range(limite):
        logger.info(
            'Consulta manifestação DF-e empresa=%s ult_nsu=%s',
            empresa.pk,
            ult_nsu,
        )
        try:
            resposta = consulta_distribuicao_dfe_nfe(comm, cnpj_dest, nsu=ult_nsu)
        except PyNFeComunicacaoError as exc:
            erros.append(str(exc))
            break

        lotes += 1
        parsed = parse_distribuicao_dfe_response(resposta)
        ult_nsu = max(ult_nsu, parsed.ult_nsu)
        salvar_estado_nsu(
            empresa.pk,
            TIPO_NFE,
            ultimo_nsu=parsed.ult_nsu,
            max_nsu=parsed.max_nsu,
            status=parsed.cstat,
            mensagem=parsed.xmotivo or parsed.mensagem_usuario,
        )

        if parsed.mensagem_usuario:
            mensagens.append(parsed.mensagem_usuario)

        for doc in parsed.documentos:
            if doc.tipo == 'RES_NFE':
                resumos += 1
                parsed_res = parse_resnfe_xml(doc.conteudo_xml)
                if not parsed_res:
                    continue
                if parsed_res.tp_amb != '1':
                    ignorados_homolog += 1
                    continue
                _, created = _upsert_resnfe(
                    empresa=empresa,
                    cnpj_dest=cnpj_dest,
                    nsu=doc.nsu,
                    parsed=parsed_res,
                )
                if created:
                    novos += 1
                else:
                    atualizados += 1
            elif doc.tipo == 'NFE':
                import xml.etree.ElementTree as ET

                try:
                    root = ET.fromstring(doc.conteudo_xml)
                    chave_el = None
                    for el in root.iter():
                        if el.tag.split('}')[-1] == 'chNFe':
                            chave_el = (el.text or '').strip()
                            break
                    if chave_el and len(chave_el) == 44:
                        obj = _marcar_xml_disponivel(
                            empresa=empresa,
                            cnpj_dest=cnpj_dest,
                            nsu=doc.nsu,
                            chave=chave_el,
                        )
                        if obj:
                            xml_disponivel += 1
                except ET.ParseError:
                    continue

        if parsed.bloquear_retentativa or parsed.aguardar_proxima_consulta:
            break
        if parsed.max_nsu <= 0 or parsed.ult_nsu >= parsed.max_nsu:
            break

    registrar_evento_manifestacao(
        None,
        empresa=empresa,
        tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.CONSULTA,
        descricao='Consulta manual de NF-e destinadas via distribuição DF-e.',
        usuario=usuario,
        ambiente='1',
        resultado_resumido=f'Novos={novos}; resumos={resumos}; xml_disponivel={xml_disponivel}',
        dados_json={
            'empresa_id': empresa.pk,
            'novos': novos,
            'atualizados': atualizados,
            'resumos': resumos,
            'xml_disponivel': xml_disponivel,
            'ignorados_homolog': ignorados_homolog,
            'lotes': lotes,
            'ult_nsu': ult_nsu,
            'mensagens': mensagens,
            'erros': erros,
        },
    )

    return {
        'sucesso': not erros or novos > 0 or resumos > 0,
        'empresa': {'id': empresa.pk, 'razao_social': empresa.razao_social, 'cnpj': empresa.cnpj},
        'novos': novos,
        'atualizados': atualizados,
        'resumos_processados': resumos,
        'xml_disponivel': xml_disponivel,
        'ignorados_homologacao': ignorados_homolog,
        'lotes_consultados': lotes,
        'ult_nsu': ult_nsu,
        'mensagens': mensagens,
        'erros': erros,
        'consultado_em': timezone.now().isoformat(),
    }
