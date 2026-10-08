"""Desfaz numeração de homologação e prepara a mesma NF-e entrada para produção."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import NFeEntrada, NFeNumeracaoConfiguracao, NFeNumeracaoNumeroLiberado
from apps.fiscal.nfe_emissao.numeracao import (
    NFeNumeracaoError,
    _serie_digits,
    _travar_config_numeracao_nfe_saida,
)

logger = logging.getLogger(__name__)

_STATUS_COM_SEFAZ = frozenset(
    {
        NFeEntrada.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
        NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        NFeEntrada.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
        NFeEntrada.StatusEmissaoSefaz.ENVIADA_PRODUCAO,
        NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        NFeEntrada.StatusEmissaoSefaz.REJEITADA_PRODUCAO,
    },
)


class NFeEntradaPrepararProducaoError(ValueError):
    pass


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _nnf_int(nf: NFeEntrada) -> int | None:
    digits = ''.join(c for c in _text(nf.numero_nfe) if c.isdigit())
    if not digits:
        return None
    return int(digits)


def entrada_teve_comunicacao_sefaz(nf: NFeEntrada) -> tuple[bool, str]:
    st = _text(nf.status_emissao_sefaz).upper()
    if st in _STATUS_COM_SEFAZ:
        return True, f'status emissão {st}'
    if _text(nf.protocolo_autorizacao):
        return True, 'protocolo de autorização'
    if _text(nf.recibo_lote):
        return True, 'recibo de lote'
    if _text(nf.xml_autorizado):
        return True, 'XML autorizado'
    if _text(nf.xml_envio_lote) or _text(nf.xml_envio):
        return True, 'XML já enviado à SEFAZ'
    if _text(nf.xml_protocolo):
        return True, 'XML de protocolo'
    cstat = _text(nf.cstat_autorizacao)
    if cstat in {'100', '150', '301', '302', '303'}:
        return True, f'cStat {cstat}'
    return False, ''


def precisa_preparar_para_producao(nf: NFeEntrada) -> bool:
    """True quando há numeração/ambiente de homologação impedindo emissão em produção."""
    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        return False
    if (nf.ambiente_emissao or '') == NFeEntrada.AmbienteEmissao.PRODUCAO and not _text(nf.numero_nfe):
        return False
    if (nf.ambiente_emissao or '') == NFeEntrada.AmbienteEmissao.HOMOLOGACAO and _text(nf.chave_acesso):
        return True
    if _text(nf.numero_nfe) and (nf.ambiente_emissao or '') != NFeEntrada.AmbienteEmissao.PRODUCAO:
        return True
    return False


def pode_preparar_entrada_para_producao(nf: NFeEntrada) -> tuple[bool, str]:
    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        return False, 'Disponível apenas para entrada própria emitida.'
    if not precisa_preparar_para_producao(nf):
        if (nf.ambiente_emissao or '') == NFeEntrada.AmbienteEmissao.PRODUCAO:
            return False, 'NF-e já está em ambiente de produção.'
        return False, 'Não há numeração de homologação para desfazer.'
    bloqueado, motivo = entrada_teve_comunicacao_sefaz(nf)
    if bloqueado:
        return (
            False,
            'Não é possível desfazer: a NF-e já teve comunicação com a SEFAZ '
            f'({motivo}). Gere uma nova NF-e para produção.',
        )
    return True, ''


def _liberar_numero_homolog_para_pool(
    nf: NFeEntrada,
    *,
    usuario=None,
) -> dict[str, Any]:
    """Devolve o nNF de homologação ao pool (ou rebobina o contador se for o último)."""
    nnf = _nnf_int(nf)
    if nnf is None or not nf.empresa_emitente_id:
        return {'liberado': False, 'motivo': 'sem_numero'}

    ambiente_orig = nf.ambiente_emissao or NFeEntrada.AmbienteEmissao.HOMOLOGACAO
    try:
        cfg = _travar_config_numeracao_nfe_saida(
            nf.empresa_emitente_id,
            ambiente=ambiente_orig,
            serie_nfe=nf.serie_nfe or None,
        )
    except NFeNumeracaoError:
        return {'liberado': False, 'motivo': 'cfg_nao_encontrada'}

    rebobinou = False
    if int(cfg.proximo_numero or 0) == nnf + 1 and int(cfg.ultimo_numero_reservado or 0) == nnf:
        cfg.proximo_numero = nnf
        cfg.ultimo_numero_reservado = nnf - 1 if nnf > 1 else None
        cfg.save(update_fields=['proximo_numero', 'ultimo_numero_reservado', 'atualizado_em'])
        rebobinou = True
        logger.info(
            'NUMERACAO_ENTRADA_HOMOLOG_REBOBINADA cfg=%s numero=%s',
            cfg.pk,
            nnf,
        )
        return {
            'liberado': True,
            'numero': nnf,
            'configuracao_id': cfg.pk,
            'rebobinou': True,
            'pool': False,
        }

    existente = (
        NFeNumeracaoNumeroLiberado.objects.select_for_update()
        .filter(configuracao_id=cfg.pk, numero=nnf, consumido_em__isnull=True)
        .first()
    )
    if existente:
        return {
            'liberado': True,
            'numero': nnf,
            'configuracao_id': cfg.pk,
            'rebobinou': False,
            'pool': True,
            'ja_no_pool': True,
        }

    row = NFeNumeracaoNumeroLiberado.objects.create(
        configuracao_id=cfg.pk,
        numero=nnf,
        nfe_saida_origem=None,
        liberado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
        motivo=(
            f'Entrada própria #{nf.pk} preparada para produção — '
            f'numeração homologação série {_serie_digits(nf.serie_nfe or cfg.serie)} liberada.'
        ),
    )
    logger.info(
        'NUMERACAO_ENTRADA_HOMOLOG_POOL cfg=%s numero=%s liberado_id=%s',
        cfg.pk,
        nnf,
        row.pk,
    )
    return {
        'liberado': True,
        'numero': nnf,
        'configuracao_id': cfg.pk,
        'rebobinou': rebobinou,
        'pool': True,
        'reutilizacao_id': row.pk,
    }


def consumir_numero_liberado_cfg(
    cfg: NFeNumeracaoConfiguracao,
) -> tuple[int, NFeNumeracaoNumeroLiberado | None]:
    """Prioriza menor número liberado do pool; senão usa proximo_numero."""
    liberado = (
        NFeNumeracaoNumeroLiberado.objects.select_for_update()
        .filter(configuracao_id=cfg.pk, consumido_em__isnull=True)
        .order_by('numero', 'pk')
        .first()
    )
    if liberado is None:
        return int(cfg.proximo_numero), None
    liberado.consumido_em = timezone.now()
    liberado.save(update_fields=['consumido_em'])
    return int(liberado.numero), liberado


@transaction.atomic
def preparar_entrada_para_producao(
    nf_entrada: NFeEntrada,
    *,
    usuario=None,
) -> dict[str, Any]:
    """
    Desfaz reserva local de homologação (sem SEFAZ) e marca a NF para produção.
    Não transmite SEFAZ; não consome número de produção ainda.
    """
    from apps.fiscal.nfe_emissao.config_producao import exigir_producao_habilitada

    nf = NFeEntrada.objects.select_for_update().get(pk=nf_entrada.pk)
    ok, motivo = pode_preparar_entrada_para_producao(nf)
    if not ok:
        # Idempotente: já em produção sem número = sucesso silencioso
        if (nf.ambiente_emissao or '') == NFeEntrada.AmbienteEmissao.PRODUCAO and not _text(nf.numero_nfe):
            return {
                'ok': True,
                'ja_pronta': True,
                'nf_entrada_id': nf.pk,
                'ambiente_emissao': nf.ambiente_emissao,
                'mensagem': 'NF-e já preparada para produção.',
            }
        raise NFeEntradaPrepararProducaoError(motivo)

    exigir_producao_habilitada()

    serie_antes = nf.serie_nfe or ''
    nnf_antes = nf.numero_nfe or ''
    chave_antes = nf.chave_acesso or ''
    ambiente_antes = nf.ambiente_emissao or ''

    liberacao = _liberar_numero_homolog_para_pool(nf, usuario=usuario)

    nf.ambiente_emissao = NFeEntrada.AmbienteEmissao.PRODUCAO
    nf.serie_nfe = ''
    nf.numero_nfe = ''
    nf.codigo_numerico = ''
    nf.chave_acesso = ''
    nf.digito_verificador = ''
    nf.numero_reservado_em = None
    nf.numero_reservado_por = None
    nf.status_emissao_sefaz = ''
    nf.xml_nfe_gerado = ''
    nf.xml_assinado = ''
    nf.xml_envio = ''
    nf.xml_retorno = ''
    nf.xml_autorizado = ''
    nf.xml_retorno_lote = ''
    nf.xml_protocolo = ''
    nf.xml_envio_lote = ''
    nf.protocolo_autorizacao = ''
    nf.cstat_autorizacao = ''
    nf.motivo_autorizacao = ''
    nf.cstat_lote = ''
    nf.xmotivo_lote = ''
    nf.recibo_lote = ''
    nf.status_operacional = NFeEntrada.StatusOperacional.RASCUNHO
    nf.save(
        update_fields=[
            'ambiente_emissao',
            'serie_nfe',
            'numero_nfe',
            'codigo_numerico',
            'chave_acesso',
            'digito_verificador',
            'numero_reservado_em',
            'numero_reservado_por',
            'status_emissao_sefaz',
            'xml_nfe_gerado',
            'xml_assinado',
            'xml_envio',
            'xml_retorno',
            'xml_autorizado',
            'xml_retorno_lote',
            'xml_protocolo',
            'xml_envio_lote',
            'protocolo_autorizacao',
            'cstat_autorizacao',
            'motivo_autorizacao',
            'cstat_lote',
            'xmotivo_lote',
            'recibo_lote',
            'status_operacional',
        ],
    )

    logger.info(
        'ENTRADA_PREPARADA_PRODUCAO nf_id=%s serie_antes=%s nnf_antes=%s chave_antes=%s liberacao=%s',
        nf.pk,
        serie_antes,
        nnf_antes,
        chave_antes[:8] if chave_antes else '',
        liberacao,
    )

    return {
        'ok': True,
        'ja_pronta': False,
        'nf_entrada_id': nf.pk,
        'ambiente_emissao': nf.ambiente_emissao,
        'ambiente_anterior': ambiente_antes,
        'serie_liberada': serie_antes,
        'numero_liberado': nnf_antes,
        'chave_anterior': chave_antes,
        'liberacao': liberacao,
        'mensagem': (
            'Numeração de homologação desfeita. NF-e pronta para reservar e emitir em produção.'
        ),
    }
