"""Persistência do resultado SEFAZ na NFeEntrada (homologação e produção)."""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeEntrada, NFeNumeracaoConfiguracao
from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz

logger = logging.getLogger(__name__)

MSG_SEM_EFEITOS_HOMOLOG = (
    'NF-e entrada própria autorizada em homologação — sem efeitos fiscais reais no ERP.'
)
MSG_SEM_EFEITOS_PRODUCAO = (
    'NF-e entrada própria autorizada em produção SEFAZ — '
    'sem efeitos automáticos de estoque/financeiro nesta fase.'
)


def _parse_dh_recbto(val: str):
    if not val:
        return None
    from django.utils.dateparse import parse_datetime

    return parse_datetime(val.replace('Z', '+00:00'))


def _atualizar_ultimo_autorizado(
    *,
    empresa: Empresa,
    ambiente: str,
    serie: str,
    numero_nfe: str,
) -> None:
    cfg = NFeNumeracaoConfiguracao.objects.filter(
        empresa_id=empresa.pk,
        ambiente=ambiente,
        modelo_documento='55',
        tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        serie=serie,
        ativo=True,
    ).first()
    if not cfg or not numero_nfe:
        return
    try:
        cfg.ultimo_numero_autorizado = int(numero_nfe)
        cfg.save(update_fields=['ultimo_numero_autorizado', 'atualizado_em'])
    except ValueError:
        pass


def aplicar_resultado_sefaz_homologacao_entrada(
    nf: NFeEntrada,
    resultado: ResultadoAutorizacaoSefaz,
    *,
    empresa: Empresa,
    usuario=None,
    xml_envio: str = '',
) -> NFeEntrada:
    del usuario  # auditoria de eventos NF-e saída não se aplica; campos SEFAZ bastam
    nf.xml_envio = xml_envio or nf.xml_envio or nf.xml_assinado or ''
    if xml_envio and '<enviNFe' in xml_envio:
        nf.xml_envio_lote = xml_envio
    nf.xml_retorno = resultado.xml_retorno_lote
    nf.xml_retorno_lote = resultado.xml_retorno_lote
    nf.xml_protocolo = resultado.xml_protocolo
    nf.cstat_lote = resultado.lote.c_stat
    nf.xmotivo_lote = resultado.lote.x_motivo
    nf.recibo_lote = resultado.recibo or resultado.lote.recibo

    nf.cstat_autorizacao = (resultado.nfe.c_stat if resultado.nfe else '') or ''
    nf.motivo_autorizacao = (resultado.nfe.x_motivo if resultado.nfe else '') or ''
    nf.protocolo_autorizacao = ''
    nf.xml_autorizado = ''
    nf.autorizada_em = None

    update_fields = [
        'xml_envio',
        'xml_envio_lote',
        'xml_retorno',
        'xml_retorno_lote',
        'xml_protocolo',
        'cstat_lote',
        'xmotivo_lote',
        'recibo_lote',
        'cstat_autorizacao',
        'motivo_autorizacao',
        'protocolo_autorizacao',
        'xml_autorizado',
        'autorizada_em',
        'status_emissao_sefaz',
        'status_operacional',
    ]

    if resultado.autorizado:
        nf.protocolo_autorizacao = resultado.protocolo
        nf.xml_autorizado = resultado.xml_autorizado
        dh = _parse_dh_recbto(resultado.nfe.dh_recbto if resultado.nfe else '')
        nf.autorizada_em = dh or timezone.now()
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.status_operacional = NFeEntrada.StatusOperacional.AUTORIZADA_HOMOLOGACAO
    elif resultado.rejeitado:
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO
        nf.status_operacional = NFeEntrada.StatusOperacional.REJEITADA
    elif resultado.status_final in (
        'AGUARDANDO_PROCESSAMENTO',
        'LOTE_PROCESSADO_SEM_PROTOCOLO',
        'ERRO_RETORNO_SEFAZ',
    ):
        nf.status_emissao_sefaz = resultado.status_final
        nf.status_operacional = NFeEntrada.StatusOperacional.ERRO_TRANSMISSAO
    else:
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO

    nf.save(update_fields=update_fields)

    if resultado.autorizado:
        _atualizar_ultimo_autorizado(
            empresa=empresa,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
            serie=nf.serie_nfe,
            numero_nfe=nf.numero_nfe,
        )

    logger.info(
        'RESULTADO_SEFAZ_ENTRADA_HOMOLOG nf_id=%s status=%s cStat_lote=%s cStat_nfe=%s protocolo=%s',
        nf.pk,
        nf.status_emissao_sefaz,
        nf.cstat_lote,
        nf.cstat_autorizacao,
        nf.protocolo_autorizacao or '',
    )
    return nf


def aplicar_resultado_sefaz_producao_entrada(
    nf: NFeEntrada,
    resultado: ResultadoAutorizacaoSefaz,
    *,
    empresa: Empresa,
    usuario=None,
    xml_envio: str = '',
) -> NFeEntrada:
    del usuario
    nf.xml_envio = xml_envio or nf.xml_envio or nf.xml_assinado or ''
    if xml_envio and '<enviNFe' in xml_envio:
        nf.xml_envio_lote = xml_envio
    nf.xml_retorno = resultado.xml_retorno_lote
    nf.xml_retorno_lote = resultado.xml_retorno_lote
    nf.xml_protocolo = resultado.xml_protocolo
    nf.cstat_lote = resultado.lote.c_stat
    nf.xmotivo_lote = resultado.lote.x_motivo
    nf.recibo_lote = resultado.recibo or resultado.lote.recibo

    nf.cstat_autorizacao = (resultado.nfe.c_stat if resultado.nfe else '') or ''
    nf.motivo_autorizacao = (resultado.nfe.x_motivo if resultado.nfe else '') or ''
    nf.protocolo_autorizacao = ''
    nf.xml_autorizado = ''
    nf.autorizada_em = None
    nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.PRODUCAO

    update_fields = [
        'xml_envio',
        'xml_envio_lote',
        'xml_retorno',
        'xml_retorno_lote',
        'xml_protocolo',
        'cstat_lote',
        'xmotivo_lote',
        'recibo_lote',
        'cstat_autorizacao',
        'motivo_autorizacao',
        'protocolo_autorizacao',
        'xml_autorizado',
        'autorizada_em',
        'status_emissao_sefaz',
        'status_operacional',
        'ambiente_emissao',
    ]

    if resultado.autorizado:
        nf.protocolo_autorizacao = resultado.protocolo
        nf.xml_autorizado = resultado.xml_autorizado
        dh = _parse_dh_recbto(resultado.nfe.dh_recbto if resultado.nfe else '')
        nf.autorizada_em = dh or timezone.now()
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
        nf.status_operacional = NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO
    elif resultado.rejeitado:
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.REJEITADA_PRODUCAO
        nf.status_operacional = NFeEntrada.StatusOperacional.REJEITADA
    elif resultado.status_final in (
        'AGUARDANDO_PROCESSAMENTO',
        'LOTE_PROCESSADO_SEM_PROTOCOLO',
        'ERRO_RETORNO_SEFAZ',
    ):
        nf.status_emissao_sefaz = resultado.status_final
        nf.status_operacional = NFeEntrada.StatusOperacional.ERRO_TRANSMISSAO
    else:
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.ENVIADA_PRODUCAO

    nf.save(update_fields=update_fields)

    if resultado.autorizado:
        _atualizar_ultimo_autorizado(
            empresa=empresa,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
            serie=nf.serie_nfe,
            numero_nfe=nf.numero_nfe,
        )

    logger.info(
        'RESULTADO_SEFAZ_ENTRADA_PRODUCAO nf_id=%s status=%s cStat_lote=%s cStat_nfe=%s protocolo=%s',
        nf.pk,
        nf.status_emissao_sefaz,
        nf.cstat_lote,
        nf.cstat_autorizacao,
        nf.protocolo_autorizacao or '',
    )
    return nf


def mensagem_resposta_resultado_entrada(resultado: ResultadoAutorizacaoSefaz) -> str:
    if resultado.autorizado:
        return 'NF-e entrada própria autorizada pela SEFAZ.'
    if resultado.rejeitado:
        motivo = (resultado.nfe.x_motivo if resultado.nfe else '') or resultado.lote.x_motivo
        return f'NF-e rejeitada pela SEFAZ: {motivo}'
    if resultado.status_final == 'LOTE_PROCESSADO_SEM_PROTOCOLO':
        return 'Lote processado sem protocolo de autorização — verifique o retorno SEFAZ.'
    if resultado.status_final == 'AGUARDANDO_PROCESSAMENTO':
        return 'Lote em processamento na SEFAZ.'
    return resultado.lote.x_motivo or 'Retorno SEFAZ recebido.'
