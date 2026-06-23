"""Manifestação manual do destinatário via evento SEFAZ."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.manifestacao_destinatario.audit import registrar_evento_manifestacao
from apps.fiscal.manifestacao_destinatario.constants import (
    CODIGO_SEFAZ_POR_EVENTO,
    DESCRICAO_EVENTO_USUARIO,
    EVENTOS_EXIGEM_JUSTIFICATIVA,
    EVENTOS_LIBERAM_DOWNLOAD_XML,
    EVENTOS_MANIFESTACAO,
    MAX_JUSTIFICATIVA,
    MIN_JUSTIFICATIVA,
    PYNFE_OPERACAO_POR_EVENTO,
    STATUS_MANIFESTACAO_POR_EVENTO,
)
from apps.fiscal.manifestacao_destinatario.manifestacao_evento_parser import (
    parse_manifestacao_evento_resposta,
)
from apps.fiscal.manifestacao_destinatario.uf_chave import (
    CORGAO_MANIFESTACAO_DESTINATARIO,
    MSG_CHAVE_UF_INVALIDA,
    UF_SERVICO_MANIFESTACAO,
    chave_prefixo_uf,
    extrair_corgao_xml_evento,
    extrair_tp_evento_xml_evento,
    garantir_corgao_ambiente_nacional,
    validar_chave_nfe_manifestacao,
)
from apps.fiscal.models import NFeDestinadaManifestacao, NFeDestinadaManifestacaoEvento
from apps.fiscal.nfe_historica_classificacao import norm_digits
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import (
    criar_comunicacao_sefaz,
    resolver_url_evento_manifestacao,
    transmitir_evento_nfe,
)

logger = logging.getLogger(__name__)

MSG_CERTIFICADO = 'Certificado digital não disponível/configurado para manifestação.'
MSG_CHAVE_INVALIDA = 'Documento sem chave de acesso válida para manifestação.'
MSG_AMBIENTE = 'Manifestação disponível apenas para NF-e de produção (tpAmb=1).'


class ManifestacaoDestinatarioError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'VALIDACAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def _validar_justificativa(evento: str, justificativa: str | None) -> str:
    if evento not in EVENTOS_EXIGEM_JUSTIFICATIVA:
        return ''
    texto = (justificativa or '').strip()
    if len(texto) < MIN_JUSTIFICATIVA:
        raise ManifestacaoDestinatarioError(
            f'Justificativa obrigatória (mínimo {MIN_JUSTIFICATIVA} caracteres).',
        )
    if len(texto) > MAX_JUSTIFICATIVA:
        raise ManifestacaoDestinatarioError(
            f'Justificativa deve ter no máximo {MAX_JUSTIFICATIVA} caracteres.',
        )
    return texto


def _montar_assinar_evento_manifestacao(
    *,
    cnpj: str,
    chave: str,
    operacao: int,
    justificativa: str,
    cert_path: str,
    senha: str,
) -> Any:
    try:
        from pynfe.entidades.evento import EventoManifestacaoDest
        from pynfe.entidades.fonte_dados import _fonte_dados
        from pynfe.processamento.assinatura import AssinaturaA1
        from pynfe.processamento.serializacao import SerializacaoXML
    except ImportError as exc:
        raise PyNFeComunicacaoError(
            f'PyNFe indisponível ({exc}). Instale PyNFe e dependências de integração SEFAZ.',
        ) from exc

    # Manifestação do destinatário: cOrgao=91 (AN) + webservice AN (PyNFe roteia tpEvento 21xxxx).
    evento = EventoManifestacaoDest(
        cnpj=cnpj,
        chave=chave,
        data_emissao=datetime.datetime.now(),
        uf=UF_SERVICO_MANIFESTACAO,
        n_seq_evento=1,
        operacao=operacao,
    )
    if justificativa:
        evento.justificativa = justificativa
    serializador = SerializacaoXML(_fonte_dados, homologacao=False)
    xml_evento = serializador.serializar_evento(evento)
    garantir_corgao_ambiente_nacional(xml_evento)
    assinador = AssinaturaA1(cert_path, senha)
    return assinador.assinar(xml_evento)


def _chave_resumida_log(chave: str) -> str:
    ch = (chave or '').strip()
    if len(ch) < 8:
        return ch[:4] + '…' if ch else '—'
    return f'{ch[:4]}…{ch[-4:]}'


def _log_pre_envio_manifestacao(
    *,
    documento_id: int,
    chave_acesso: str,
    evento_norm: str,
    codigo: str,
    evento_assinado: Any,
    comunicacao: Any,
) -> None:
    corgao_xml = extrair_corgao_xml_evento(evento_assinado)
    tp_evento = extrair_tp_evento_xml_evento(evento_assinado)
    endpoint = resolver_url_evento_manifestacao(comunicacao)
    logger.info(
        'Manifestação pre-envio doc=%s chave_prefixo_uf=%s chave_resumida=%s '
        'cOrgao_final_no_xml=%s tpEvento=%s codigo_evento=%s evento=%s '
        'uf_servico_manifestacao=%s endpoint=%s ambiente=1',
        documento_id,
        chave_prefixo_uf(chave_acesso),
        _chave_resumida_log(chave_acesso),
        corgao_xml or CORGAO_MANIFESTACAO_DESTINATARIO,
        tp_evento or codigo,
        codigo,
        evento_norm,
        UF_SERVICO_MANIFESTACAO.upper(),
        endpoint or 'AN/EVENTOS',
    )


def _pode_manifestar(documento: NFeDestinadaManifestacao, evento: str) -> None:
    if len((documento.chave_acesso or '').strip()) != 44:
        raise ManifestacaoDestinatarioError(MSG_CHAVE_INVALIDA)
    if documento.ambiente != NFeDestinadaManifestacao.Ambiente.PRODUCAO:
        raise ManifestacaoDestinatarioError(MSG_AMBIENTE)
    status_final = {
        NFeDestinadaManifestacao.StatusManifestacao.CONFIRMADA,
        NFeDestinadaManifestacao.StatusManifestacao.DESCONHECIDA,
        NFeDestinadaManifestacao.StatusManifestacao.NAO_REALIZADA,
    }
    if documento.status_manifestacao in status_final:
        raise ManifestacaoDestinatarioError(
            'Documento já possui manifestação final registrada.',
        )


def _evento_ja_registrado_historico(documento: NFeDestinadaManifestacao, codigo: str) -> bool:
    return documento.eventos.filter(
        tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.MANIFESTACAO,
        codigo_evento=codigo,
    ).exists()


def _persistir_erro_comunicacao(
    documento_id: int,
    *,
    evento_norm: str,
    codigo: str,
    usuario,
    exc: Exception,
) -> None:
    with transaction.atomic():
        documento = NFeDestinadaManifestacao.objects.select_for_update().get(pk=documento_id)
        documento.status_manifestacao = NFeDestinadaManifestacao.StatusManifestacao.ERRO
        documento.ultimo_xmotivo = str(exc)[:255]
        documento.save(update_fields=['status_manifestacao', 'ultimo_xmotivo', 'consultado_em'])
        registrar_evento_manifestacao(
            documento,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.MANIFESTACAO,
            descricao=DESCRICAO_EVENTO_USUARIO.get(evento_norm, evento_norm),
            usuario=usuario,
            codigo_evento=codigo,
            resultado_resumido='Erro SEFAZ',
            xmotivo=str(exc)[:255],
            dados_json={'evento': evento_norm, 'erro': str(exc)},
        )


def _persistir_rejeicao_sefaz(
    documento_id: int,
    *,
    evento_norm: str,
    codigo: str,
    usuario,
    parsed,
) -> None:
    cstat = parsed.cstat_efetivo
    xmotivo = parsed.xmotivo_efetivo
    with transaction.atomic():
        documento = NFeDestinadaManifestacao.objects.select_for_update().get(pk=documento_id)
        documento.status_manifestacao = NFeDestinadaManifestacao.StatusManifestacao.ERRO
        documento.ultimo_cstat = cstat
        documento.ultimo_xmotivo = xmotivo[:255]
        documento.save(
            update_fields=['status_manifestacao', 'ultimo_cstat', 'ultimo_xmotivo', 'consultado_em'],
        )
        registrar_evento_manifestacao(
            documento,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.MANIFESTACAO,
            descricao=DESCRICAO_EVENTO_USUARIO.get(evento_norm, evento_norm),
            usuario=usuario,
            codigo_evento=codigo,
            cstat=cstat,
            xmotivo=xmotivo,
            resultado_resumido='Rejeitado SEFAZ',
            dados_json={
                'evento': evento_norm,
                'protocolo': parsed.protocolo,
                'cStat_lote': parsed.c_stat_lote,
                'xMotivo_lote': parsed.x_motivo_lote,
            },
        )


def _persistir_sucesso_manifestacao(
    documento_id: int,
    *,
    evento_norm: str,
    codigo: str,
    usuario,
    parsed,
    justificativa_limpa: str,
) -> NFeDestinadaManifestacaoEvento | None:
    cstat = parsed.c_stat_evento or parsed.cstat_efetivo
    xmotivo = parsed.xmotivo_efetivo
    resultado_resumido = (
        'Evento já registrado anteriormente'
        if parsed.duplicidade
        else 'Manifestação registrada'
    )
    with transaction.atomic():
        documento = NFeDestinadaManifestacao.objects.select_for_update().get(pk=documento_id)
        agora = timezone.now()
        documento.status_manifestacao = STATUS_MANIFESTACAO_POR_EVENTO[evento_norm]
        documento.manifestado_em = agora
        documento.ultimo_cstat = cstat
        documento.ultimo_xmotivo = xmotivo[:255]
        update_fields = [
            'status_manifestacao',
            'manifestado_em',
            'ultimo_cstat',
            'ultimo_xmotivo',
            'consultado_em',
        ]
        if (
            evento_norm in EVENTOS_LIBERAM_DOWNLOAD_XML
            and documento.status_xml
            not in (
                NFeDestinadaManifestacao.StatusXml.BAIXADO,
                NFeDestinadaManifestacao.StatusXml.DISPONIVEL,
            )
        ):
            documento.status_xml = NFeDestinadaManifestacao.StatusXml.DISPONIVEL
            update_fields.append('status_xml')
        documento.save(update_fields=update_fields)

        if _evento_ja_registrado_historico(documento, codigo):
            return None

        return registrar_evento_manifestacao(
            documento,
            tipo_acao=NFeDestinadaManifestacaoEvento.TipoAcao.MANIFESTACAO,
            descricao=DESCRICAO_EVENTO_USUARIO.get(evento_norm, evento_norm),
            usuario=usuario,
            codigo_evento=codigo,
            cstat=cstat,
            xmotivo=xmotivo,
            resultado_resumido=resultado_resumido,
            dados_json={
                'evento': evento_norm,
                'protocolo': parsed.protocolo,
                'justificativa': justificativa_limpa or None,
                'cStat_lote': parsed.c_stat_lote,
                'xMotivo_lote': parsed.x_motivo_lote,
                'duplicidade': parsed.duplicidade,
            },
        )


def manifestar_documento_destinatario(
    documento: NFeDestinadaManifestacao,
    *,
    evento: str,
    justificativa: str = '',
    confirmacao_explicita: bool = False,
    usuario=None,
    transmitir_fn=None,
) -> dict[str, Any]:
    evento_norm = (evento or '').strip().upper()
    if evento_norm not in EVENTOS_MANIFESTACAO:
        raise ManifestacaoDestinatarioError('Tipo de evento de manifestação inválido.')
    if not confirmacao_explicita:
        raise ManifestacaoDestinatarioError(
            'Confirmação explícita obrigatória para registrar manifestação.',
        )

    with transaction.atomic():
        documento = NFeDestinadaManifestacao.objects.select_for_update().select_related('empresa').get(
            pk=documento.pk,
        )
        _pode_manifestar(documento, evento_norm)
        justificativa_limpa = _validar_justificativa(evento_norm, justificativa)
        documento_id = documento.pk
        chave_acesso = documento.chave_acesso
        empresa = documento.empresa

    cnpj = norm_digits(empresa.cnpj)
    if len(cnpj) != 14:
        raise ManifestacaoDestinatarioError('CNPJ da empresa inválido.')

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise ManifestacaoDestinatarioError(MSG_CERTIFICADO) from exc
    if not cert_info.valido:
        raise ManifestacaoDestinatarioError(MSG_CERTIFICADO)

    try:
        chave_acesso = validar_chave_nfe_manifestacao(documento.chave_acesso or '')
    except ValueError as exc:
        raise ManifestacaoDestinatarioError(str(exc) or MSG_CHAVE_UF_INVALIDA) from exc

    senha = (empresa.senha_certificado or '').strip()
    operacao = PYNFE_OPERACAO_POR_EVENTO[evento_norm]
    codigo = CODIGO_SEFAZ_POR_EVENTO[evento_norm]

    evento_assinado = _montar_assinar_evento_manifestacao(
        cnpj=cnpj,
        chave=chave_acesso,
        operacao=operacao,
        justificativa=justificativa_limpa,
        cert_path=cert_info.caminho,
        senha=senha,
    )

    comm = criar_comunicacao_sefaz(
        UF_SERVICO_MANIFESTACAO,
        cert_info.caminho,
        senha,
        homologacao=False,
    )
    _log_pre_envio_manifestacao(
        documento_id=documento_id,
        chave_acesso=chave_acesso,
        evento_norm=evento_norm,
        codigo=codigo,
        evento_assinado=evento_assinado,
        comunicacao=comm,
    )

    if transmitir_fn is None:
        transmitir_fn = lambda ev: transmitir_evento_nfe(comm, ev)

    try:
        resposta = transmitir_fn(evento_assinado)
    except PyNFeComunicacaoError as exc:
        _persistir_erro_comunicacao(
            documento_id,
            evento_norm=evento_norm,
            codigo=codigo,
            usuario=usuario,
            exc=exc,
        )
        raise ManifestacaoDestinatarioError(str(exc), etapa='SEFAZ') from exc

    parsed = parse_manifestacao_evento_resposta(resposta)

    if not parsed.aceito:
        msg = parsed.xmotivo_efetivo or 'SEFAZ não aceitou o evento de manifestação.'
        if parsed.c_stat_lote and not parsed.c_stat_evento:
            msg = (
                f'{msg} Verifique o retorno individual do evento '
                f'(cStat lote {parsed.c_stat_lote} não confirma manifestação).'
            )
        _persistir_rejeicao_sefaz(
            documento_id,
            evento_norm=evento_norm,
            codigo=codigo,
            usuario=usuario,
            parsed=parsed,
        )
        cstat_msg = parsed.cstat_efetivo
        raise ManifestacaoDestinatarioError(
            msg if not cstat_msg else f'{msg} (cStat {cstat_msg}).',
            etapa='SEFAZ',
        )

    evt = _persistir_sucesso_manifestacao(
        documento_id,
        evento_norm=evento_norm,
        codigo=codigo,
        usuario=usuario,
        parsed=parsed,
        justificativa_limpa=justificativa_limpa,
    )

    documento = NFeDestinadaManifestacao.objects.get(pk=documento_id)
    cstat = parsed.c_stat_evento or parsed.cstat_efetivo
    xmotivo = parsed.xmotivo_efetivo

    logger.info(
        'Manifestação destinatário doc=%s chave_resumida=%s evento=%s cStat_evento=%s cStat_lote=%s '
        'chave_prefixo_uf=%s cOrgao_final_no_xml=%s uf_servico=%s cStat=%s xMotivo=%s',
        documento.pk,
        _chave_resumida_log(documento.chave_acesso or ''),
        evento_norm,
        parsed.c_stat_evento,
        parsed.c_stat_lote,
        chave_prefixo_uf(chave_acesso),
        CORGAO_MANIFESTACAO_DESTINATARIO,
        UF_SERVICO_MANIFESTACAO.upper(),
        cstat,
        xmotivo[:120] if xmotivo else '',
    )

    return {
        'documento_id': documento.pk,
        'evento': evento_norm,
        'status_manifestacao': documento.status_manifestacao,
        'status_manifestacao_label': documento.get_status_manifestacao_display(),
        'cstat': cstat,
        'cstat_lote': parsed.c_stat_lote,
        'cstat_evento': parsed.c_stat_evento,
        'xmotivo': xmotivo,
        'protocolo': parsed.protocolo,
        'evento_id': evt.pk if evt else None,
        'duplicidade': parsed.duplicidade,
    }
