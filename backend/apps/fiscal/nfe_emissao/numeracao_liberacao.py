"""Liberação e reutilização de numeração NF-e Saída nunca transmitida à SEFAZ — ERP 4.0.15.2.23."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeNumeracaoNumeroLiberado, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_emissao.numeracao import _nnf_str, _serie_digits, obter_config_numeracao
from apps.fiscal.nfe_saida_ciclo_vida import STATUS_NFE_DESCARTADA_INTERNA, nf_possui_autorizacao_sefaz_efetiva
from apps.fiscal.nfe_saida_envio_email import nf_inutilizada_operacional
from apps.fiscal.nfe_saida_efeitos import _registrar_evento

logger = logging.getLogger(__name__)

_STATUS_EMISSAO_BLOQUEIA_REUTILIZACAO = frozenset(
    {
        NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
        NFeSaida.StatusEmissaoSefaz.ENVIADA_PRODUCAO,
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        NFeSaida.StatusEmissaoSefaz.AGUARDANDO_PROCESSAMENTO,
        NFeSaida.StatusEmissaoSefaz.LOTE_PROCESSADO_SEM_PROTOCOLO,
    },
)

_CSTAT_DENEGACAO = frozenset({'301', '302', '303'})


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _norm(st: str | None) -> str:
    return _text(st).upper()


def nf_teve_comunicacao_sefaz_ou_incerta(nf: NFeSaida) -> tuple[bool, str]:
    """True quando há indício de comunicação SEFAZ ou status fiscal incerto."""
    if nf_possui_autorizacao_sefaz_efetiva(nf):
        return True, 'NF-e possui autorização ou protocolo SEFAZ.'
    if nf_inutilizada_operacional(nf):
        return True, 'NF-e inutilizada.'
    if _text(nf.protocolo_autorizacao):
        return True, 'protocolo de autorização informado'
    if _text(getattr(nf, 'protocolo_cancelamento', None)):
        return True, 'protocolo de cancelamento informado'
    if _text(nf.recibo_lote):
        return True, 'recibo de lote SEFAZ'
    if _text(nf.xml_envio_lote):
        return True, 'XML de envio à SEFAZ'
    if _text(nf.xml_autorizado):
        return True, 'XML autorizado com protocolo'
    if _text(nf.xml_protocolo):
        return True, 'XML de protocolo SEFAZ'
    cstat = _text(nf.cstat_autorizacao)
    if cstat == '100':
        return True, 'cStat 100 (autorizada)'
    if cstat in _CSTAT_DENEGACAO:
        return True, f'cStat {cstat} (denegada)'
    if _text(nf.cstat_lote):
        return True, f'cStat de lote ({nf.cstat_lote})'
    sefaz = _norm(nf.status_emissao_sefaz)
    if sefaz in _STATUS_EMISSAO_BLOQUEIA_REUTILIZACAO:
        return True, f'status emissão SEFAZ {nf.status_emissao_sefaz}'
    if sefaz == NFeSaida.StatusEmissaoSefaz.XML_ASSINADO and _text(nf.xml_envio_lote):
        return True, 'XML assinado e enviado à SEFAZ'
    st = _norm(nf.status)
    if st in ('CANCELADA', 'CANCELADO', 'CANCELADA_HOMOLOGACAO', 'CANCELADA_PRODUCAO'):
        return True, f'NF-e cancelada ({nf.status})'
    if st in ('DENEGADA', 'INUTILIZADA'):
        return True, f'status {nf.status}'
    return False, ''


def nf_pode_liberar_numero_fiscal(nf: NFeSaida) -> tuple[bool, str]:
    if not _text(nf.numero_nfe):
        return False, 'NF-e sem numeração fiscal reservada.'
    bloqueado, motivo = nf_teve_comunicacao_sefaz_ou_incerta(nf)
    if bloqueado:
        return (
            False,
            'Número não pode ser reutilizado porque a NF-e já teve comunicação com a SEFAZ '
            f'ou status fiscal não confirmado ({motivo}).',
        )
    if NFeNumeracaoNumeroLiberado.objects.filter(
        nfe_saida_origem_id=nf.pk,
        consumido_em__isnull=True,
    ).exists():
        return True, ''
    return True, ''


def _resolver_config_numeracao_nf(nf: NFeSaida) -> NFeNumeracaoConfiguracao | None:
    if not nf.empresa_emitente_id or not nf.ambiente_emissao or not nf.serie_nfe:
        return None
    try:
        return obter_config_numeracao(
            nf.empresa_emitente_id,
            ambiente=nf.ambiente_emissao,
            modelo='55',
        )
    except Exception:
        return (
            NFeNumeracaoConfiguracao.objects.filter(
                empresa_id=nf.empresa_emitente_id,
                ambiente=nf.ambiente_emissao,
                modelo_documento='55',
                tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
                serie=_serie_digits(nf.serie_nfe),
                ativo=True,
            )
            .first()
        )


def _numero_inteiro_nf(nf: NFeSaida) -> int | None:
    digits = ''.join(c for c in _text(nf.numero_nfe) if c.isdigit())
    if not digits:
        return None
    return int(digits)


@transaction.atomic
def liberar_numero_fiscal_apos_descarte(
    nf: NFeSaida,
    *,
    motivo: str,
    usuario=None,
) -> dict[str, Any] | None:
    """
    Coloca o nNF da NF-e descartada no pool de reutilização.
    Idempotente por NF-e origem. Retorna None se não havia numeração a liberar.
    """
    pode, msg = nf_pode_liberar_numero_fiscal(nf)
    if not pode:
        logger.warning('NUMERACAO_NAO_LIBERADA nfe_id=%s motivo=%s', nf.pk, msg)
        return {'liberado': False, 'motivo_bloqueio': msg}

    numero = _numero_inteiro_nf(nf)
    if numero is None:
        return None

    cfg = _resolver_config_numeracao_nf(nf)
    if cfg is None:
        logger.warning('NUMERACAO_NAO_LIBERADA nfe_id=%s cfg_nao_encontrada', nf.pk)
        return {'liberado': False, 'motivo_bloqueio': 'Configuração de numeração não encontrada.'}

    existente = (
        NFeNumeracaoNumeroLiberado.objects.select_for_update()
        .filter(nfe_saida_origem_id=nf.pk, consumido_em__isnull=True)
        .first()
    )
    if existente:
        return {
            'liberado': True,
            'numero': existente.numero,
            'configuracao_id': cfg.pk,
            'reutilizacao_id': existente.pk,
            'ja_liberado': True,
        }

    if NFeNumeracaoNumeroLiberado.objects.filter(
        configuracao_id=cfg.pk,
        numero=numero,
        consumido_em__isnull=True,
    ).exists():
        logger.warning(
            'NUMERACAO_JA_NO_POOL cfg=%s numero=%s nfe_origem=%s',
            cfg.pk,
            numero,
            nf.pk,
        )
        return {
            'liberado': True,
            'numero': numero,
            'configuracao_id': cfg.pk,
            'ja_liberado': True,
        }

    row = NFeNumeracaoNumeroLiberado.objects.create(
        configuracao_id=cfg.pk,
        numero=numero,
        nfe_saida_origem_id=nf.pk,
        liberado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
        motivo=motivo,
    )
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.NUMERACAO_LIBERADA_DESCARTE,
        status_novo=nf.status or STATUS_NFE_DESCARTADA_INTERNA,
        resumo={
            'numero_nfe': _nnf_str(numero),
            'serie_nfe': nf.serie_nfe,
            'ambiente_emissao': nf.ambiente_emissao,
            'configuracao_id': cfg.pk,
            'reutilizacao_id': row.pk,
            'sem_transmissao_sefaz': True,
            'mensagem': (
                f'Número fiscal {numero} liberado para reutilização na série {nf.serie_nfe} '
                f'({nf.ambiente_emissao}).'
            ),
        },
        observacao=motivo,
        usuario=usuario,
    )
    return {
        'liberado': True,
        'numero': numero,
        'configuracao_id': cfg.pk,
        'reutilizacao_id': row.pk,
        'ja_liberado': False,
    }


def reservar_numero_liberado_disponivel(
    cfg: NFeNumeracaoConfiguracao,
    *,
    nfe_saida: NFeSaida,
    usuario=None,
) -> tuple[int, NFeNumeracaoNumeroLiberado | None]:
    """
    Retorna (número, registro_liberado ou None).
    Prioriza o menor número liberado disponível no pool.
    """
    liberado = (
        NFeNumeracaoNumeroLiberado.objects.select_for_update()
        .filter(configuracao_id=cfg.pk, consumido_em__isnull=True)
        .order_by('numero', 'pk')
        .first()
    )
    if liberado is None:
        return int(cfg.proximo_numero), None

    agora = timezone.now()
    liberado.consumido_em = agora
    liberado.nfe_saida_consumo_id = nfe_saida.pk
    liberado.save(update_fields=['consumido_em', 'nfe_saida_consumo'])

    _registrar_evento(
        nfe_saida,
        tipo=NFeSaidaEvento.TipoEvento.NUMERACAO_REUTILIZADA,
        status_novo=nfe_saida.status_emissao_sefaz or NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA,
        resumo={
            'numero_nfe': _nnf_str(liberado.numero),
            'serie_nfe': _serie_digits(cfg.serie),
            'ambiente_emissao': cfg.ambiente,
            'nfe_saida_origem_id': liberado.nfe_saida_origem_id,
            'reutilizacao_id': liberado.pk,
            'mensagem': (
                f'Número fiscal {liberado.numero} reutilizado de descarte local '
                f'(NF-e origem #{liberado.nfe_saida_origem_id or "—"}).'
            ),
        },
        observacao='Numeração reutilizada de NF-e descartada sem transmissão SEFAZ.',
        usuario=usuario,
    )
    return int(liberado.numero), liberado
