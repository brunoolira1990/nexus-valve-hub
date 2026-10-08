"""
ERP 4.0.13.6.8 — Ciclo de vida pré-autorização SEFAZ (estorno faturamento / descarte rascunho).

Descarte interno ≠ cancelamento fiscal SEFAZ.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_bloqueio import STATUS_NFE_RASCUNHO, nf_autorizada_homologacao
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO as STATUS_RASCUNHO_FAT
from apps.fiscal.nfe_saida_efeitos import _lock_faturamento, _lock_nfe_saida, _nf_autorizada_interna

STATUS_NFE_DESCARTADA_INTERNA = 'DESCARTADA_INTERNA'
MOTIVO_MIN_CARACTERES = 10

_STATUS_BLOQUEIA_DESCARTE = frozenset(
    {
        'EMITIDA',
        'EMITIDO',
        'AUTORIZADA',
        'AUTORIZADA_INTERNA',
        'AUTORIZADA_HOMOLOGACAO',
        'AUTORIZADA_PRODUCAO',
        'CANCELADA_INTERNA',
        'CANCELADA',
        'CANCELADO',
        STATUS_NFE_DESCARTADA_INTERNA,
    },
)

_STATUS_PERMITE_DESCARTE = frozenset(
    {
        STATUS_NFE_RASCUNHO,
        STATUS_RASCUNHO_FAT,
        'EM_CONFERENCIA',
        'COM_PENDENCIAS',
        'CONFERIDA',
        'PRONTA_PARA_EMISSAO',
        'ERRO_VALIDACAO',
        'ERRO_TRANSMISSAO',
        'REJEITADA_HOMOLOGACAO',
        'REJEITADA',
    },
)


def _norm(st: str | None) -> str:
    return (st or '').strip().upper()


def validar_motivo_estorno_ou_descarte(motivo: str) -> str:
    texto = (motivo or '').strip()
    if len(texto) < MOTIVO_MIN_CARACTERES:
        raise ValueError('Informe um motivo com pelo menos 10 caracteres.')
    return texto


def nf_possui_autorizacao_sefaz_efetiva(nf: NFeSaida) -> bool:
    if nf_autorizada_homologacao(nf):
        return True
    if _nf_autorizada_interna(nf):
        return True
    if (nf.protocolo_autorizacao or '').strip():
        return True
    if (nf.xml_autorizado or '').strip():
        return True
    if (nf.cstat_autorizacao or '').strip() == '100':
        return True
    st = _norm(nf.status)
    if st in ('EMITIDA', 'AUTORIZADA', 'AUTORIZADA_INTERNA', 'AUTORIZADA_HOMOLOGACAO', 'AUTORIZADA_PRODUCAO'):
        return True
    if (nf.status_emissao_sefaz or '').strip() == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        return True
    return False


def nf_esta_descartada_ou_inativa(nf: NFeSaida | None) -> bool:
    if not nf:
        return True
    return _norm(nf.status) in (
        STATUS_NFE_DESCARTADA_INTERNA,
        'CANCELADA_INTERNA',
        'CANCELADA',
        'CANCELADO',
        'CANCELADA_PRODUCAO',
        'CANCELADA_HOMOLOGACAO',
    )


def avaliar_descarte_nfe_rascunho(nf: NFeSaida) -> tuple[bool, str]:
    st = _norm(nf.status)
    if st == STATUS_NFE_DESCARTADA_INTERNA:
        return False, 'NF-e rascunho já foi descartada internamente.'
    if nf_possui_autorizacao_sefaz_efetiva(nf):
        return False, 'Não é possível descartar: NF-e possui autorização ou protocolo SEFAZ.'
    sefaz_st = (nf.status_emissao_sefaz or '').strip()
    if sefaz_st in (
        NFeSaida.StatusEmissaoSefaz.AGUARDANDO_PROCESSAMENTO,
        NFeSaida.StatusEmissaoSefaz.LOTE_PROCESSADO_SEM_PROTOCOLO,
    ):
        return (
            False,
            'NF-e com processamento SEFAZ pendente ou incerto. Consulte a situação antes de descartar.',
        )
    if st in ('CANCELADA_INTERNA', 'CANCELADA', 'CANCELADO'):
        return False, 'NF-e já está cancelada internamente.'
    if st in _STATUS_BLOQUEIA_DESCARTE:
        return False, f'NF-e em status {nf.status} não permite descarte interno.'
    if st in _STATUS_PERMITE_DESCARTE:
        return True, ''
    if st == STATUS_NFE_RASCUNHO:
        return True, ''
    return False, f'Status {nf.status} não permite descarte de rascunho.'


def avaliar_estorno_faturamento(
    *,
    faturamento: FaturamentoPedidoVenda,
    nf: NFeSaida | None = None,
) -> tuple[bool, str]:
    from apps.comercial.faturamento_pedido_venda import calcular_estorno_restante_faturamento
    from apps.fiscal.nfe_saida_pedido_cancelamento import faturamento_teve_estorno_por_cancelamento_nfe

    if faturamento.status == FaturamentoPedidoVenda.Status.CANCELADO:
        return False, 'Faturamento já foi estornado.'
    if faturamento_teve_estorno_por_cancelamento_nfe(faturamento):
        return (
            False,
            'Saldo comercial já liberado após cancelamento da NF-e. Use Emitir nova NF-e.',
        )
    _, estorno_ja_aplicado = calcular_estorno_restante_faturamento(faturamento)
    if estorno_ja_aplicado and faturamento.status in (
        FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE,
        FaturamentoPedidoVenda.Status.GERADO_NFE,
    ):
        return False, 'Faturamento já estornado ou liberado — quantidades do pedido já estão coerentes.'
    if faturamento.status == FaturamentoPedidoVenda.Status.RASCUNHO:
        return True, ''
    if faturamento.status not in (
        FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE,
        FaturamentoPedidoVenda.Status.GERADO_NFE,
    ):
        return False, f'Status {faturamento.status} não permite estorno.'
    nf = nf or (faturamento.nfe_saida if faturamento.nfe_saida_id else None)
    if nf and not nf_esta_descartada_ou_inativa(nf):
        if nf_possui_autorizacao_sefaz_efetiva(nf):
            return False, 'Não é possível estornar: existe NF-e autorizada. Use fluxo fiscal de cancelamento.'
        pode, msg = avaliar_descarte_nfe_rascunho(nf)
        if not pode:
            return False, msg
    return True, ''


def _registrar_evento_nfe(
    nf: NFeSaida,
    *,
    tipo: str,
    status_anterior: str,
    status_novo: str,
    motivo: str,
    usuario=None,
    resumo: dict[str, Any] | None = None,
) -> NFeSaidaEvento:
    payload = dict(resumo or {})
    payload.setdefault('motivo', motivo)
    payload.setdefault('sem_evento_sefaz', True)
    return NFeSaidaEvento.objects.create(
        nfe_saida=nf,
        tipo_evento=tipo,
        pedido_venda_id=nf.pedido_venda_id,
        faturamento_pedido_venda_id=nf.faturamento_pedido_venda_id,
        status_anterior=status_anterior,
        status_novo=status_novo,
        resumo=payload,
        observacao=motivo,
        criado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
    )


def _marcar_nfe_descartada_interna(
    nf: NFeSaida,
    *,
    motivo: str,
    usuario=None,
    tipo_evento: str = NFeSaidaEvento.TipoEvento.DESCARTE_RASCUNHO_NFE,
) -> NFeSaida:
    status_anterior = nf.status or ''
    agora = timezone.now()
    nf.status = STATUS_NFE_DESCARTADA_INTERNA
    nf.motivo_cancelamento = motivo
    nf.cancelada_em = agora
    nf.cancelada_por = usuario if usuario and getattr(usuario, 'is_authenticated', False) else None
    interno = (nf.observacoes_internas or '').strip()
    marca = f'[Descarte interno {agora:%d/%m/%Y %H:%M}] {motivo}'
    nf.observacoes_internas = f'{interno}\n{marca}'.strip() if interno else marca
    nf.save(
        update_fields=[
            'status',
            'motivo_cancelamento',
            'cancelada_em',
            'cancelada_por',
            'observacoes_internas',
        ],
    )
    _registrar_evento_nfe(
        nf,
        tipo=tipo_evento,
        status_anterior=status_anterior,
        status_novo=nf.status,
        motivo=motivo,
        usuario=usuario,
        resumo={
            'mensagem': (
                f'NF-e rascunho {nf.numero} descartada internamente. '
                'Nenhum evento SEFAZ foi enviado.'
            ),
        },
    )
    return nf


def _liberar_faturamento_para_nova_nfe(fat: FaturamentoPedidoVenda) -> None:
    if fat.status != FaturamentoPedidoVenda.Status.GERADO_NFE:
        return
    fat.nfe_saida_id = None
    fat.nfe_saida_gerada_em = None
    fat.status = FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE
    fat.save(update_fields=['nfe_saida', 'nfe_saida_gerada_em', 'status', 'atualizado_em'])


def _append_obs_pedido(pedido: PedidoVenda, linha: str) -> None:
    base = (pedido.observacoes_internas or '').strip()
    pedido.observacoes_internas = f'{base}\n{linha}'.strip() if base else linha
    pedido.save(update_fields=['observacoes_internas'])


@transaction.atomic
def descartar_nfe_rascunho(
    nf: NFeSaida,
    *,
    motivo: str,
    usuario=None,
    liberar_faturamento: bool = True,
) -> dict[str, Any]:
    motivo = validar_motivo_estorno_ou_descarte(motivo)
    nf = _lock_nfe_saida(nf.pk)
    pode, msg = avaliar_descarte_nfe_rascunho(nf)
    if not pode:
        raise ValueError(msg)

    status_anterior = nf.status or ''
    _marcar_nfe_descartada_interna(nf, motivo=motivo, usuario=usuario)

    from apps.fiscal.nfe_emissao.numeracao_liberacao import liberar_numero_fiscal_apos_descarte

    liberacao = liberar_numero_fiscal_apos_descarte(nf, motivo=motivo, usuario=usuario)

    fat_id = nf.faturamento_pedido_venda_id
    pedido_id = nf.pedido_venda_id
    if liberar_faturamento and fat_id:
        fat = _lock_faturamento(fat_id)
        if fat.nfe_saida_id == nf.pk:
            _liberar_faturamento_para_nova_nfe(fat)

    mensagens = [
        'NF-e rascunho descartada internamente. '
        'Nenhum evento foi enviado à SEFAZ porque a NF-e não estava autorizada.',
    ]
    if liberacao and liberacao.get('liberado') and liberacao.get('numero'):
        mensagens.append(
            f'Número fiscal {liberacao["numero"]} liberado e poderá ser reutilizado na próxima NF-e '
            f'da mesma série e ambiente.',
        )
    elif liberacao and liberacao.get('motivo_bloqueio'):
        mensagens.append(liberacao['motivo_bloqueio'])

    return {
        'nfe_saida_id': nf.pk,
        'status_anterior': status_anterior,
        'status': nf.status,
        'pedido_id': pedido_id,
        'faturamento_id': fat_id,
        'numeracao_liberada': liberacao,
        'mensagem': mensagens[0] + (
            f' {mensagens[1]}' if len(mensagens) > 1 else ''
        ),
        'mensagens': mensagens,
    }


def descartar_nfe_no_estorno_faturamento(
    nf: NFeSaida,
    *,
    motivo: str,
    usuario=None,
    faturamento: FaturamentoPedidoVenda,
) -> None:
    """Descarta NF-e vinculada ao estornar faturamento (sem liberar faturamento para nova NF-e)."""
    nf = _lock_nfe_saida(nf.pk)
    pode, msg = avaliar_descarte_nfe_rascunho(nf)
    if not pode:
        raise ValueError(msg)
    _marcar_nfe_descartada_interna(
        nf,
        motivo=motivo,
        usuario=usuario,
        tipo_evento=NFeSaidaEvento.TipoEvento.ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE,
    )
    from apps.fiscal.nfe_emissao.numeracao_liberacao import liberar_numero_fiscal_apos_descarte

    liberar_numero_fiscal_apos_descarte(nf, motivo=motivo, usuario=usuario)
    faturamento.nfe_saida_id = None
    faturamento.nfe_saida_gerada_em = None
    faturamento.save(update_fields=['nfe_saida', 'nfe_saida_gerada_em', 'atualizado_em'])
