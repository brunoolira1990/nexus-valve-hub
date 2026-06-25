"""Persistência do resultado SEFAZ (lote vs protocolo NF-e) na NFeSaida."""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz
from apps.fiscal.nfe_saida_efeitos import _registrar_evento

logger = logging.getLogger(__name__)

MSG_SEM_EFEITOS_REAIS = (
    'NF-e autorizada em homologação — sem efeitos fiscais reais no ERP (estoque/financeiro).'
)


def _parse_dh_recbto(val: str):
    if not val:
        return None
    from django.utils.dateparse import parse_datetime

    dt = parse_datetime(val.replace('Z', '+00:00'))
    return dt


def _sincronizar_pedido_pos_autorizacao_sefaz(nf: NFeSaida) -> None:
    """Recalcula status/quantidades do pedido após autorização SEFAZ (sem efeitos estoque/financeiro)."""
    if not nf.pedido_venda_id:
        return
    from apps.comercial.faturamento_pedido_venda import sincronizar_pedido_com_nfe_fiscal_ativa

    sincronizar_pedido_com_nfe_fiscal_ativa(nf.pedido_venda_id)


def aplicar_resultado_sefaz_homologacao(
    nf: NFeSaida,
    resultado: ResultadoAutorizacaoSefaz,
    *,
    empresa: Empresa,
    usuario=None,
    xml_envio: str = '',
) -> NFeSaida:
    """Grava campos separados lote/NF-e e define status final conforme infProt."""
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
    ]

    status = resultado.status_final
    if status == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        nf.protocolo_autorizacao = resultado.protocolo
        nf.xml_autorizado = resultado.xml_autorizado
        dh = _parse_dh_recbto(resultado.nfe.dh_recbto if resultado.nfe else '')
        nf.autorizada_em = dh or timezone.now()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        nf.status = 'AUTORIZADA_HOMOLOGACAO'
        update_fields.append('status')
    elif status == NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO:
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO
    elif status in ('AGUARDANDO_PROCESSAMENTO', 'LOTE_PROCESSADO_SEM_PROTOCOLO', 'ERRO_RETORNO_SEFAZ'):
        nf.status_emissao_sefaz = status
    else:
        nf.status_emissao_sefaz = status or NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO

    nf.save(update_fields=update_fields)

    _registrar_evento(
        nf,
        tipo='NFE_ENVIADA_HOMOLOGACAO',
        status_novo=nf.status_emissao_sefaz,
        resumo={
            'cStat_lote': resultado.lote.c_stat,
            'xMotivo_lote': resultado.lote.x_motivo,
            'cStat_nfe': nf.cstat_autorizacao,
            'xMotivo_nfe': nf.motivo_autorizacao,
            'recibo': nf.recibo_lote,
        },
        usuario=usuario,
    )

    if resultado.autorizado:
        cfg = NFeNumeracaoConfiguracao.objects.filter(
            empresa_id=empresa.pk,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
            modelo_documento='55',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie=nf.serie_nfe,
            ativo=True,
        ).first()
        if cfg and nf.numero_nfe:
            try:
                n_int = int(nf.numero_nfe)
                cfg.ultimo_numero_autorizado = n_int
                cfg.save(update_fields=['ultimo_numero_autorizado', 'atualizado_em'])
            except ValueError:
                pass
        _registrar_evento(
            nf,
            tipo='NFE_AUTORIZADA_HOMOLOGACAO',
            status_novo=nf.status_emissao_sefaz,
            resumo={
                'protocolo': nf.protocolo_autorizacao,
                'cStat_lote': nf.cstat_lote,
                'xMotivo_lote': nf.xmotivo_lote,
                'cStat_nfe': nf.cstat_autorizacao,
                'xMotivo_nfe': nf.motivo_autorizacao,
                'serie_nfe': nf.serie_nfe,
                'numero_nfe': nf.numero_nfe,
                'chave_acesso': nf.chave_acesso,
                'ambiente': 'homologacao',
            },
            observacao=MSG_SEM_EFEITOS_REAIS,
            usuario=usuario,
        )
    elif resultado.rejeitado:
        _registrar_evento(
            nf,
            tipo='NFE_REJEITADA_HOMOLOGACAO',
            status_novo=nf.status_emissao_sefaz,
            resumo={
                'cStat_lote': nf.cstat_lote,
                'xMotivo_lote': nf.xmotivo_lote,
                'cStat_nfe': nf.cstat_autorizacao,
                'xMotivo_nfe': nf.motivo_autorizacao,
            },
            usuario=usuario,
        )

    logger.info(
        'RESULTADO_SEFAZ_APLICADO nfe_id=%s status=%s cStat_lote=%s cStat_nfe=%s protocolo=%s',
        nf.pk,
        nf.status_emissao_sefaz,
        nf.cstat_lote,
        nf.cstat_autorizacao,
        nf.protocolo_autorizacao or '',
    )
    if resultado.autorizado:
        _sincronizar_pedido_pos_autorizacao_sefaz(nf)
    return nf


MSG_SEM_EFEITOS_PRODUCAO = (
    'NF-e autorizada em produção SEFAZ — sem efeitos automáticos de estoque/financeiro/apuração nesta fase.'
)


def aplicar_resultado_sefaz_producao(
    nf: NFeSaida,
    resultado: ResultadoAutorizacaoSefaz,
    *,
    empresa: Empresa,
    usuario=None,
    xml_envio: str = '',
) -> NFeSaida:
    """Grava protocolo/cStat/XML autorizado produção — sem estoque/financeiro/apuração."""
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
        'ambiente_emissao',
    ]

    if resultado.autorizado:
        nf.protocolo_autorizacao = resultado.protocolo
        nf.xml_autorizado = resultado.xml_autorizado
        dh = _parse_dh_recbto(resultado.nfe.dh_recbto if resultado.nfe else '')
        nf.autorizada_em = dh or timezone.now()
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
        nf.status = 'AUTORIZADA_PRODUCAO'
        nf.ambiente_emissao = NFeSaida.AmbienteEmissao.PRODUCAO
        update_fields.extend(['status'])
    elif resultado.rejeitado:
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_PRODUCAO
    elif resultado.status_final in ('AGUARDANDO_PROCESSAMENTO', 'LOTE_PROCESSADO_SEM_PROTOCOLO', 'ERRO_RETORNO_SEFAZ'):
        nf.status_emissao_sefaz = resultado.status_final
    else:
        nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.ENVIADA_PRODUCAO

    nf.save(update_fields=update_fields)

    _registrar_evento(
        nf,
        tipo='NFE_ENVIADA_PRODUCAO',
        status_novo=nf.status_emissao_sefaz,
        resumo={
            'cStat_lote': resultado.lote.c_stat,
            'xMotivo_lote': resultado.lote.x_motivo,
            'cStat_nfe': nf.cstat_autorizacao,
            'xMotivo_nfe': nf.motivo_autorizacao,
            'recibo': nf.recibo_lote,
            'ambiente': 'producao',
        },
        usuario=usuario,
    )

    if resultado.autorizado:
        cfg = NFeNumeracaoConfiguracao.objects.filter(
            empresa_id=empresa.pk,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
            modelo_documento='55',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie=nf.serie_nfe,
            ativo=True,
        ).first()
        if cfg and nf.numero_nfe:
            try:
                n_int = int(nf.numero_nfe)
                cfg.ultimo_numero_autorizado = n_int
                cfg.save(update_fields=['ultimo_numero_autorizado', 'atualizado_em'])
            except ValueError:
                pass
        _registrar_evento(
            nf,
            tipo='NFE_AUTORIZADA_PRODUCAO',
            status_novo=nf.status_emissao_sefaz,
            resumo={
                'protocolo': nf.protocolo_autorizacao,
                'cStat_lote': nf.cstat_lote,
                'xMotivo_lote': nf.xmotivo_lote,
                'cStat_nfe': nf.cstat_autorizacao,
                'xMotivo_nfe': nf.motivo_autorizacao,
                'serie_nfe': nf.serie_nfe,
                'numero_nfe': nf.numero_nfe,
                'chave_acesso': nf.chave_acesso,
                'ambiente': 'producao',
            },
            observacao=MSG_SEM_EFEITOS_PRODUCAO,
            usuario=usuario,
        )
    elif resultado.rejeitado:
        _registrar_evento(
            nf,
            tipo='NFE_REJEITADA_PRODUCAO',
            status_novo=nf.status_emissao_sefaz,
            resumo={
                'cStat_lote': nf.cstat_lote,
                'xMotivo_lote': nf.xmotivo_lote,
                'cStat_nfe': nf.cstat_autorizacao,
                'xMotivo_nfe': nf.motivo_autorizacao,
                'ambiente': 'producao',
            },
            usuario=usuario,
        )

    logger.info(
        'RESULTADO_SEFAZ_PRODUCAO_APLICADO nfe_id=%s status=%s cStat_lote=%s cStat_nfe=%s protocolo=%s',
        nf.pk,
        nf.status_emissao_sefaz,
        nf.cstat_lote,
        nf.cstat_autorizacao,
        nf.protocolo_autorizacao or '',
    )
    if resultado.autorizado:
        _sincronizar_pedido_pos_autorizacao_sefaz(nf)
        try:
            from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe

            resolver_xml_autorizado_danfe(nf, persistir=True)
        except Exception:
            logger.warning(
                'Não foi possível gravar procNFe completo após autorização produção nfe_id=%s',
                nf.pk,
                exc_info=True,
            )
    return nf


def mensagem_resposta_resultado_producao(resultado: ResultadoAutorizacaoSefaz) -> str:
    if resultado.autorizado:
        return MSG_SEM_EFEITOS_PRODUCAO
    if resultado.nfe and resultado.nfe.c_stat:
        return f'NF-e rejeitada em produção — cStat {resultado.nfe.c_stat}: {resultado.nfe.x_motivo}'
    if resultado.status_final == 'LOTE_PROCESSADO_SEM_PROTOCOLO':
        return 'Lote processado pela SEFAZ produção, mas protocolo da NF-e não encontrado no retorno.'
    if resultado.status_final == 'AGUARDANDO_PROCESSAMENTO':
        recibo = resultado.recibo or resultado.lote.recibo
        return f'Lote recebido/em processamento pela SEFAZ produção. Recibo: {recibo or "—"}.'
    if resultado.lote.c_stat:
        return f'Retorno SEFAZ produção — lote cStat {resultado.lote.c_stat}: {resultado.lote.x_motivo}'
    return 'Transmissão produção não concluída pela SEFAZ.'


def mensagem_resposta_resultado(resultado: ResultadoAutorizacaoSefaz) -> str:
    if resultado.autorizado:
        return MSG_SEM_EFEITOS_REAIS
    if resultado.nfe and resultado.nfe.c_stat:
        return f'NF-e rejeitada — cStat {resultado.nfe.c_stat}: {resultado.nfe.x_motivo}'
    if resultado.status_final == 'LOTE_PROCESSADO_SEM_PROTOCOLO':
        return 'Lote processado pela SEFAZ, mas protocolo da NF-e não encontrado no retorno.'
    if resultado.status_final == 'AGUARDANDO_PROCESSAMENTO':
        recibo = resultado.recibo or resultado.lote.recibo
        return f'Lote recebido/em processamento pela SEFAZ. Recibo: {recibo or "—"}.'
    if resultado.lote.c_stat:
        return f'Retorno SEFAZ — lote cStat {resultado.lote.c_stat}: {resultado.lote.x_motivo}'
    return 'Transmissão não concluída pela SEFAZ.'


def resultado_tem_resolucao_final(resultado: ResultadoAutorizacaoSefaz) -> bool:
    return resultado.autorizado or resultado.rejeitado
