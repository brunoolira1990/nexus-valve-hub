"""NF-e Saída 3.1 — política de efeitos de autorização/cancelamento (sem SEFAZ, estoque ou financeiro real)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.comercial.faturamento_pedido_venda import (
    _round_qty,
    recalcular_status_item,
    recalcular_status_pedido,
)
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO

STATUS_NFE_AUTORIZADA_INTERNA = 'AUTORIZADA_INTERNA'
STATUS_NFE_CANCELADA_INTERNA = 'CANCELADA_INTERNA'

MSG_ESTOQUE_FUTURO = 'Baixa de estoque será implementada em fase futura (sem movimentação nesta etapa).'
MSG_FINANCEIRO_FUTURO = 'Contas a receber será implementado em fase futura (sem lançamento nesta etapa).'
MSG_NAO_TRANSMITE_SEFAZ = 'Esta operação não transmite para a SEFAZ e não gera protocolo fiscal.'


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _norm_status(st: str | None) -> str:
    return (st or '').strip().upper()


def _nf_cancelada(st: str) -> bool:
    return st in ('CANCELADA', 'CANCELADA_INTERNA', 'CANCELADO') or 'CANCELAD' in st


def _nf_autorizada_interna(nf: NFeSaida) -> bool:
    st = _norm_status(nf.status)
    return st == STATUS_NFE_AUTORIZADA_INTERNA or bool(nf.efeitos_autorizacao_aplicados_em)


def _registrar_evento(
    nf: NFeSaida,
    *,
    tipo: str,
    status_anterior: str = '',
    status_novo: str = '',
    resumo: dict | None = None,
    observacao: str = '',
    usuario=None,
) -> NFeSaidaEvento:
    return NFeSaidaEvento.objects.create(
        nfe_saida=nf,
        tipo_evento=tipo,
        pedido_venda_id=nf.pedido_venda_id,
        faturamento_pedido_venda_id=nf.faturamento_pedido_venda_id,
        status_anterior=status_anterior,
        status_novo=status_novo,
        resumo=resumo,
        observacao=observacao,
        criado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
    )


def _lock_nfe_saida(nfe_id: int) -> NFeSaida:
    """Lock apenas na tabela NF-e (sem select_related em FK nullable — evita FOR UPDATE em outer join)."""
    return NFeSaida.objects.select_for_update().get(pk=nfe_id)


def _lock_faturamento(faturamento_id: int) -> FaturamentoPedidoVenda:
    return FaturamentoPedidoVenda.objects.select_for_update().get(pk=faturamento_id)


def _lock_pedido(pedido_id: int) -> PedidoVenda:
    return PedidoVenda.objects.select_for_update().get(pk=pedido_id)


def _itens_nf_para_estorno(nf: NFeSaida) -> list[ItemNFeSaida]:
    return list(
        ItemNFeSaida.objects.filter(nf_id=nf.pk)
        .select_related('item_faturamento_pedido', 'produto')
        .order_by('id'),
    )


def _efeitos_autorizacao_previstos(nf: NFeSaida, pedido: PedidoVenda | None, fat: FaturamentoPedidoVenda | None) -> list[str]:
    linhas = [
        'Marcar NF-e como autorizada internamente (simulação pré-SEFAZ).',
        MSG_NAO_TRANSMITE_SEFAZ,
        'Não altera quantidade_faturada do pedido (já confirmada no faturamento).',
    ]
    if fat:
        linhas.append('Manter faturamento vinculado travado para cancelamento simples de rascunho.')
    if pedido:
        linhas.append(f'Pedido permanecerá com status operacional conforme saldo: {pedido.status or "—"}.')
    return linhas


def _efeitos_cancelamento_previstos() -> list[str]:
    return [
        'Cancelar NF-e manterá o documento no histórico.',
        'Estornará quantidade_faturada dos itens do pedido conforme itens da NF-e.',
        'Recalculará status dos itens e do pedido de venda.',
        'Liberará saldo para novo faturamento e nova NF-e (não reutiliza a cancelada).',
        MSG_NAO_TRANSMITE_SEFAZ,
    ]


def avaliar_efeitos_nfe_saida(nfe_saida: NFeSaida | int) -> dict[str, Any]:
    """Política prevista — leitura; não altera banco."""
    if isinstance(nfe_saida, int):
        nf = (
            NFeSaida.objects.select_related('pedido_venda', 'faturamento_pedido_venda')
            .prefetch_related('itens')
            .get(pk=nfe_saida)
        )
    else:
        nf = nfe_saida

    st = _norm_status(nf.status)
    pedido = nf.pedido_venda
    fat = nf.faturamento_pedido_venda
    alertas: list[str] = []

    pode_autorizar = (
        st == STATUS_NFE_RASCUNHO
        and not nf.efeitos_autorizacao_aplicados_em
        and not _nf_cancelada(st)
        and fat is not None
        and fat.status == FaturamentoPedidoVenda.Status.GERADO_NFE
        and fat.nfe_saida_id == nf.pk
    )
    if st != STATUS_NFE_RASCUNHO and not _nf_autorizada_interna(nf):
        alertas.append('Autorização interna exige NF-e em rascunho vinculada a faturamento confirmado.')
    if not fat:
        alertas.append('NF-e sem faturamento vinculado: política de estorno no cancelamento não se aplica.')
    elif fat.nfe_saida_id != nf.pk:
        alertas.append('Faturamento vinculado diverge desta NF-e.')

    pode_cancelar = _nf_autorizada_interna(nf) and not _nf_cancelada(st) and bool(fat)
    if _nf_cancelada(st):
        alertas.append('NF-e já está cancelada.')
    elif not _nf_autorizada_interna(nf):
        alertas.append('Cancelamento interno exige efeitos de autorização já aplicados.')

    atend_count = nf.atendimentos_estoque.exclude(status=AtendimentoEstoque.Status.CANCELADO).count()
    if atend_count:
        alertas.append(
            f'Existem {atend_count} atendimento(s) de estoque vinculados; estorno físico não é aplicado nesta fase.',
        )

    return {
        'nfe_saida_id': nf.pk,
        'numero': nf.numero,
        'status': nf.status,
        'pedido_id': nf.pedido_venda_id,
        'faturamento_id': nf.faturamento_pedido_venda_id,
        'pode_aplicar_autorizacao': pode_autorizar,
        'pode_cancelar': pode_cancelar,
        'efeitos_autorizacao': _efeitos_autorizacao_previstos(nf, pedido, fat),
        'efeitos_cancelamento': _efeitos_cancelamento_previstos(),
        'estoque': {
            'aplicacao_real': False,
            'mensagem': MSG_ESTOQUE_FUTURO,
        },
        'financeiro': {
            'aplicacao_real': False,
            'mensagem': MSG_FINANCEIRO_FUTURO,
        },
        'alertas': alertas,
    }


def _nome_usuario_evento(usuario) -> str:
    if not usuario:
        return ''
    nome = (getattr(usuario, 'get_full_name', lambda: '')() or '').strip()
    if nome:
        return nome
    return (getattr(usuario, 'username', None) or getattr(usuario, 'email', None) or '').strip()


def listar_eventos_nfe_saida(nfe_saida_id: int) -> list[dict[str, Any]]:
    """Mais recente primeiro (ordem para UI)."""
    return [
        {
            'id': ev.pk,
            'tipo_evento': ev.tipo_evento,
            'status_anterior': ev.status_anterior,
            'status_novo': ev.status_novo,
            'observacao': ev.observacao,
            'resumo': ev.resumo,
            'criado_por_nome': _nome_usuario_evento(ev.criado_por),
            'criado_em': ev.criado_em.isoformat(),
        }
        for ev in (
            NFeSaidaEvento.objects.filter(nfe_saida_id=nfe_saida_id)
            .select_related('criado_por')
            .order_by('-criado_em', '-id')
        )
    ]


def montar_payload_eventos_nfe_saida(nfe_saida_id: int) -> dict[str, Any]:
    return {
        'nfe_saida_id': nfe_saida_id,
        'eventos': listar_eventos_nfe_saida(nfe_saida_id),
    }


class EfeitosAplicadosDict(TypedDict):
    nfe_saida_id: int
    status: str
    pedido_id: int | None
    faturamento_id: int | None
    mensagens: list[str]


@transaction.atomic
def aplicar_efeitos_autorizacao_nfe_saida(
    nfe_saida: NFeSaida | int,
    *,
    usuario=None,
    observacao: str = '',
) -> EfeitosAplicadosDict:
    """
    Simulação interna dos efeitos pós-autorização.
    Não transmite SEFAZ, não duplica quantidade_faturada, não movimenta estoque/financeiro.
    """
    nf_id = nfe_saida.pk if isinstance(nfe_saida, NFeSaida) else int(nfe_saida)
    nf = _lock_nfe_saida(nf_id)
    st_antes = nf.status or ''

    if _nf_cancelada(st_antes):
        raise ValueError('NF-e cancelada não pode receber efeitos de autorização.')
    if nf.efeitos_autorizacao_aplicados_em:
        raise ValueError('Efeitos de autorização já foram aplicados nesta NF-e.')
    if _norm_status(st_antes) != STATUS_NFE_RASCUNHO:
        raise ValueError('Somente NF-e em rascunho pode receber autorização interna nesta fase.')

    if not nf.faturamento_pedido_venda_id:
        raise ValueError('NF-e deve estar vinculada a um faturamento de pedido de venda.')
    fat = _lock_faturamento(nf.faturamento_pedido_venda_id)
    if fat.status != FaturamentoPedidoVenda.Status.GERADO_NFE or fat.nfe_saida_id != nf.pk:
        raise ValueError('Faturamento deve estar com NF-e gerada e vinculada a esta nota.')

    agora = timezone.now()
    nf.status = STATUS_NFE_AUTORIZADA_INTERNA
    nf.efeitos_autorizacao_aplicados_em = agora
    nf.save(update_fields=['status', 'efeitos_autorizacao_aplicados_em'])

    if nf.pedido_venda_id:
        pedido = _lock_pedido(nf.pedido_venda_id)
        recalcular_status_pedido(pedido)

    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.AUTORIZACAO_EFEITOS_APLICADOS,
        status_anterior=st_antes,
        status_novo=nf.status,
        resumo={
            'estoque_aplicado': False,
            'financeiro_aplicado': False,
            'quantidade_faturada_duplicada': False,
        },
        observacao=observacao or MSG_NAO_TRANSMITE_SEFAZ,
        usuario=usuario,
    )

    return {
        'nfe_saida_id': nf.pk,
        'status': nf.status,
        'pedido_id': nf.pedido_venda_id,
        'faturamento_id': fat.pk,
        'mensagens': [
            'Efeitos de autorização interna aplicados.',
            MSG_NAO_TRANSMITE_SEFAZ,
            MSG_ESTOQUE_FUTURO,
            MSG_FINANCEIRO_FUTURO,
        ],
    }


@transaction.atomic
def aplicar_efeitos_cancelamento_nfe_saida(
    nfe_saida: NFeSaida | int,
    motivo: str,
    *,
    usuario=None,
) -> EfeitosAplicadosDict:
    """
    Simulação interna de cancelamento: estorna quantidade_faturada, recalcula pedido, mantém histórico.
    """
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValueError('Informe o motivo do cancelamento.')

    nf_id = nfe_saida.pk if isinstance(nfe_saida, NFeSaida) else int(nfe_saida)
    nf = _lock_nfe_saida(nf_id)
    st_antes = nf.status or ''

    if _nf_cancelada(st_antes) or nf.efeitos_cancelamento_aplicados_em:
        raise ValueError('NF-e já está cancelada ou efeitos de cancelamento já foram aplicados.')
    if not _nf_autorizada_interna(nf):
        raise ValueError('Cancelamento interno exige autorização interna prévia (efeitos aplicados).')

    if not nf.faturamento_pedido_venda_id:
        raise ValueError('NF-e sem faturamento vinculado: não é possível estornar quantidades do pedido.')
    fat = _lock_faturamento(nf.faturamento_pedido_venda_id)

    itens_nf = _itens_nf_para_estorno(nf)
    if not itens_nf:
        raise ValueError('NF-e sem itens para estorno de faturamento.')

    estorno_resumo: list[dict[str, Any]] = []
    pedido_ids_afetados: set[int] = set()

    for linha_nf in itens_nf:
        qtd = _round_qty(_dec(linha_nf.quantidade))
        if qtd <= 0:
            continue
        item_fat = linha_nf.item_faturamento_pedido
        if not item_fat or not item_fat.item_pedido_id:
            raise ValueError(
                f'Item da NF-e #{linha_nf.pk} sem vínculo com item de faturamento/pedido; estorno abortado.',
            )
        item_pedido = ItemPedidoVenda.objects.select_for_update().get(pk=item_fat.item_pedido_id)
        if item_pedido.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            raise ValueError(f'Item do pedido {item_pedido.pk} está cancelado.')

        qtd_antes = _dec(item_pedido.quantidade_faturada)
        nova_qtd = max(Decimal('0'), _round_qty(qtd_antes - qtd))
        item_pedido.quantidade_faturada = nova_qtd
        item_pedido.save(update_fields=['quantidade_faturada'])
        recalcular_status_item(item_pedido)
        pedido_ids_afetados.add(item_pedido.pedido_id)
        estorno_resumo.append(
            {
                'item_pedido_id': item_pedido.pk,
                'quantidade_estornada': str(qtd),
                'quantidade_faturada_antes': str(qtd_antes),
                'quantidade_faturada_depois': str(nova_qtd),
            }
        )

    if not estorno_resumo:
        raise ValueError('Nenhuma quantidade foi estornada nos itens do pedido.')

    agora = timezone.now()
    nf.status = STATUS_NFE_CANCELADA_INTERNA
    nf.motivo_cancelamento = motivo
    nf.cancelada_em = agora
    nf.efeitos_cancelamento_aplicados_em = agora
    if usuario and getattr(usuario, 'is_authenticated', False):
        nf.efeitos_cancelamento_por = usuario
        nf.cancelada_por = usuario
    nf.save(
        update_fields=[
            'status',
            'motivo_cancelamento',
            'cancelada_em',
            'cancelada_por',
            'efeitos_cancelamento_aplicados_em',
            'efeitos_cancelamento_por',
        ],
    )

    for pid in sorted(pedido_ids_afetados):
        pedido = _lock_pedido(pid)
        recalcular_status_pedido(pedido)

    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.ESTORNO_FATURAMENTO,
        status_anterior=st_antes,
        status_novo=nf.status,
        resumo={'itens_estornados': estorno_resumo},
        observacao=motivo,
        usuario=usuario,
    )
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.CANCELAMENTO_EFEITOS_APLICADOS,
        status_anterior=st_antes,
        status_novo=nf.status,
        observacao=motivo,
        usuario=usuario,
    )

    return {
        'nfe_saida_id': nf.pk,
        'status': nf.status,
        'pedido_id': nf.pedido_venda_id,
        'faturamento_id': fat.pk,
        'mensagens': [
            'Cancelamento interno aplicado; quantidades faturadas estornadas no pedido.',
            'Saldo liberado para novo faturamento.',
            MSG_NAO_TRANSMITE_SEFAZ,
            MSG_ESTOQUE_FUTURO,
            MSG_FINANCEIRO_FUTURO,
        ],
    }
