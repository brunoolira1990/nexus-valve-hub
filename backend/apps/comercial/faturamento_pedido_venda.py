"""Pedido Venda 3 — faturamento parcial (solicitação, sem NF-e/estoque/financeiro)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.db.models import Sum

from apps.comercial.models import (
    FaturamentoPedidoVenda,
    ItemFaturamentoPedidoVenda,
    ItemPedidoVenda,
    PedidoVenda,
)
from apps.comercial.pedido_venda_totais import calcular_totais_pedido_venda
from apps.fiscal.models import NFeSaida

STATUS_PEDIDO_FATURADO = frozenset({'faturado', 'FATURADO'})
STATUS_PEDIDO_CANCELADO = frozenset({'cancelado', 'cancelada', 'CANCELADO'})
STATUS_PEDIDO_BLOQUEIO_FAT = STATUS_PEDIDO_FATURADO | STATUS_PEDIDO_CANCELADO

MSG_FATURAMENTO_CRIADO = (
    'Solicitação de faturamento criada. A emissão da NF-e será tratada em etapa posterior.'
)


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _duplicatas_nfe_faturamento(nf: NFeSaida) -> list[dict[str, str]]:
    from apps.fiscal.nfe_saida_duplicatas import duplicatas_nfe_para_api

    return duplicatas_nfe_para_api(nf)


def _round_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'))


def _round_qty(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.001'))


def quantidade_pedida_item(item: ItemPedidoVenda) -> Decimal:
    return _round_qty(_dec(item.quantidade_negociada or item.quantidade))


def quantidade_pendente_item(item: ItemPedidoVenda) -> Decimal:
    return max(Decimal('0'), quantidade_pedida_item(item) - _dec(item.quantidade_faturada))


def preco_unitario_item(item: ItemPedidoVenda) -> Decimal:
    return _dec(item.preco_por_unidade_negociada or item.valor_unitario)


def _status_pedido_normalizado(pedido: PedidoVenda) -> str:
    return (pedido.status or '').strip()


def pedido_permite_faturamento(pedido: PedidoVenda) -> tuple[bool, str]:
    st = _status_pedido_normalizado(pedido).upper()
    if st in STATUS_PEDIDO_CANCELADO:
        return False, 'Pedido cancelado não pode gerar faturamento.'
    if st in STATUS_PEDIDO_FATURADO:
        return False, 'Pedido já está totalmente faturado.'
    itens_ativos = pedido.itens.exclude(status_item=ItemPedidoVenda.StatusItem.CANCELADO)
    if not itens_ativos.exists():
        return False, 'Pedido sem itens ativos para faturar.'
    if all(quantidade_pendente_item(it) <= 0 for it in itens_ativos):
        return False, 'Pedido já está totalmente faturado (todos os itens).'
    return True, ''


def quantidade_reservada_rascunho(
    pedido: PedidoVenda,
    item_pedido_id: int,
    *,
    exclude_faturamento_id: int | None = None,
) -> Decimal:
    qs = ItemFaturamentoPedidoVenda.objects.filter(
        faturamento__pedido_id=pedido.pk,
        faturamento__status=FaturamentoPedidoVenda.Status.RASCUNHO,
        item_pedido_id=item_pedido_id,
    )
    if exclude_faturamento_id:
        qs = qs.exclude(faturamento_id=exclude_faturamento_id)
    total = qs.aggregate(s=Sum('quantidade'))['s']
    return _round_qty(_dec(total))


def quantidade_disponivel_faturar(item: ItemPedidoVenda) -> Decimal:
    pendente = quantidade_pendente_item(item)
    reservado = quantidade_reservada_rascunho(item.pedido, item.pk)
    return max(Decimal('0'), pendente - reservado)


def _desconto_proporcional(item: ItemPedidoVenda, quantidade: Decimal) -> Decimal:
    pedida = quantidade_pedida_item(item)
    if pedida <= 0:
        return Decimal('0')
    return _round_money(_dec(item.desconto) * (quantidade / pedida))


def _valor_item_faturamento(item: ItemPedidoVenda, quantidade: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    preco = preco_unitario_item(item)
    desconto = _desconto_proporcional(item, quantidade)
    valor = _round_money(quantidade * preco - desconto)
    return preco, desconto, valor


def _snapshot_cliente(pedido: PedidoVenda) -> dict[str, Any]:
    cli = pedido.cliente
    return {
        'cliente_id': cli.pk,
        'razao_social': cli.razao_social,
        'nome_fantasia': getattr(cli, 'nome_fantasia', '') or '',
        'cnpj': getattr(cli, 'cnpj', '') or '',
        'uf': getattr(cli, 'uf', '') or '',
    }


def recalcular_status_item(item: ItemPedidoVenda) -> None:
    if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
        return
    pendente = quantidade_pendente_item(item)
    faturada = _dec(item.quantidade_faturada)
    if faturada <= 0:
        item.status_item = ItemPedidoVenda.StatusItem.PENDENTE
    elif pendente <= 0:
        item.status_item = ItemPedidoVenda.StatusItem.FATURADO
    else:
        item.status_item = ItemPedidoVenda.StatusItem.PARCIAL
    item.save(update_fields=['status_item'])


def recalcular_status_pedido(pedido: PedidoVenda) -> None:
    st_atual = _status_pedido_normalizado(pedido).upper()
    if st_atual in STATUS_PEDIDO_CANCELADO:
        return

    itens = list(pedido.itens.exclude(status_item=ItemPedidoVenda.StatusItem.CANCELADO))
    if not itens:
        return

    todos_faturados = all(it.status_item == ItemPedidoVenda.StatusItem.FATURADO for it in itens)
    algum_faturado = any(
        it.status_item in (ItemPedidoVenda.StatusItem.FATURADO, ItemPedidoVenda.StatusItem.PARCIAL)
        for it in itens
    )
    tem_rascunho = pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.RASCUNHO).exists()

    if todos_faturados:
        novo = 'FATURADO'
    elif algum_faturado:
        novo = 'PARCIALMENTE_FATURADO'
    elif tem_rascunho:
        novo = 'EM_FATURAMENTO'
    elif st_atual in ('PARCIALMENTE_FATURADO', 'FATURADO', 'EM_FATURAMENTO'):
        novo = 'ABERTO'
    else:
        novo = pedido.status or 'ABERTO'

    pedido.status = novo
    pedido.save(update_fields=['status'])


def _valor_faturado_item(item: ItemPedidoVenda) -> Decimal:
    """Valor já faturado do item (com desconto proporcional à qty faturada)."""
    faturada = _dec(item.quantidade_faturada)
    if faturada <= 0:
        return Decimal('0')
    return _valor_item_faturamento(item, faturada)[2]


def _valor_pendente_item(item: ItemPedidoVenda) -> Decimal:
    pendente = quantidade_pendente_item(item)
    if pendente <= 0:
        return Decimal('0')
    return _valor_item_faturamento(item, pendente)[2]


def _serializar_item_resumo(item: ItemPedidoVenda) -> dict[str, Any]:
    pedida = quantidade_pedida_item(item)
    faturada = _dec(item.quantidade_faturada)
    pendente = quantidade_pendente_item(item)
    disponivel = quantidade_disponivel_faturar(item)
    preco = preco_unitario_item(item)
    produto = item.produto
    return {
        'item_pedido_id': item.pk,
        'produto_codigo': (produto.codigo_completo if produto else '') or '',
        'descricao': (produto.descricao if produto else '') or '',
        'quantidade_pedida': str(pedida),
        'quantidade_faturada': str(_round_qty(faturada)),
        'quantidade_pendente': str(pendente),
        'quantidade_disponivel': str(disponivel),
        'status_item': item.status_item,
        'valor_unitario': str(_round_money(preco)),
        'valor_pendente': str(_round_money(_valor_pendente_item(item))),
    }


def montar_resumo_faturamento(pedido: PedidoVenda) -> dict[str, Any]:
    from apps.fiscal.nfe_saida_pedido_cancelamento import sincronizar_efeitos_comerciais_pedido

    sincronizar_efeitos_comerciais_pedido(pedido)

    pedido = (
        PedidoVenda.objects.select_related('cliente')
        .prefetch_related('itens__produto', 'faturamentos')
        .get(pk=pedido.pk)
    )
    itens = list(pedido.itens.select_related('produto').order_by('id'))
    valor_faturado = Decimal('0')
    valor_pendente = Decimal('0')
    itens_pendentes = itens_parciais = itens_faturados = 0

    itens_resumo = []
    for item in itens:
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            continue
        row = _serializar_item_resumo(item)
        itens_resumo.append(row)
        valor_faturado += _valor_faturado_item(item)
        valor_pendente += _valor_pendente_item(item)
        if item.status_item == ItemPedidoVenda.StatusItem.FATURADO:
            itens_faturados += 1
        elif item.status_item == ItemPedidoVenda.StatusItem.PARCIAL:
            itens_parciais += 1
        else:
            itens_pendentes += 1

    rascunhos = [
        {
            'faturamento_id': f.pk,
            'numero_faturamento': (f.numero_faturamento or '').strip(),
            'status': f.status,
            'observacao': f.observacao,
            'criado_em': f.criado_em.isoformat(),
            'itens_count': f.itens.count(),
        }
        for f in pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.RASCUNHO).order_by('-id')
    ]

    from apps.fiscal.nfe_emissao.cancelamento_dados import montar_resumo_cancelamento_nfe_saida
    from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
    from apps.fiscal.nfe_saida_ciclo_vida import avaliar_estorno_faturamento
    from apps.fiscal.nfe_saida_pedido_cancelamento import nf_cancelada_sefaz

    faturamentos_nfe = []
    for f in (
        pedido.faturamentos.filter(
            status__in=(
                FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE,
                FaturamentoPedidoVenda.Status.GERADO_NFE,
            ),
        )
        .select_related('nfe_saida', 'nfe_saida__pedido_venda', 'nfe_saida__faturamento_pedido_venda')
        .order_by('-id')
    ):
        pode_estornar, motivo_bloqueio_estorno = avaliar_estorno_faturamento(faturamento=f, nf=f.nfe_saida)
        cancel_resumo = (
            montar_resumo_cancelamento_nfe_saida(f.nfe_saida) if f.nfe_saida_id and f.nfe_saida else {}
        )
        nfe_cancelada = bool(cancel_resumo.get('cancelada')) or (
            f.nfe_saida_id and nf_cancelada_sefaz(f.nfe_saida)
        )
        faturamentos_nfe.append(
            {
                'faturamento_id': f.pk,
                'numero_faturamento': (f.numero_faturamento or '').strip(),
                'status': f.status,
                'observacao': f.observacao,
                'criado_em': f.criado_em.isoformat(),
                'itens_count': f.itens.count(),
                'pode_estornar_pre_autorizacao': pode_estornar,
                'motivo_bloqueio_estorno': motivo_bloqueio_estorno,
                'nfe_saida_id': f.nfe_saida_id,
                'nfe_saida_numero': f.nfe_saida.numero if f.nfe_saida_id else '',
                'nfe_saida_status': f.nfe_saida.status if f.nfe_saida_id else '',
                'nfe_cancelada_sefaz': nfe_cancelada,
                'nfe_protocolo_cancelamento': (cancel_resumo.get('protocolo_cancelamento') or '').strip(),
                'nfe_motivo_cancelamento': (cancel_resumo.get('motivo_cancelamento') or '').strip(),
                'nfe_cancelada_em': cancel_resumo.get('cancelada_em'),
                'pode_gerar_nova_nfe': (
                    f.status == FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE and not f.nfe_saida_id
                ),
                **(
                    {
                        'nfe_titulo_exibicao': ap['titulo_exibicao'],
                        'nfe_numero_fiscal': ap['numero_fiscal'],
                        'nfe_serie_fiscal': ap['serie_fiscal'],
                        'nfe_status_emissao_sefaz': ap['status_emissao_sefaz'],
                        'nfe_cstat': (f.nfe_saida.cstat_autorizacao or '') if f.nfe_saida_id else '',
                        'duplicatas_nfe': _duplicatas_nfe_faturamento(f.nfe_saida),
                    }
                    if f.nfe_saida_id
                    and (ap := montar_apresentacao_nfe_saida(f.nfe_saida))
                    else {}
                ),
            },
        )

    pode, motivo = pedido_permite_faturamento(pedido)

    inconsistencias: list[dict[str, str]] = []
    for f in pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.GERADO_NFE):
        if not f.nfe_saida_id and not NFeSaida.objects.filter(faturamento_pedido_venda_id=f.pk).exists():
            inconsistencias.append(
                {
                    'codigo': 'fat_gerado_nfe_sem_vinculo',
                    'bloqueia_geracao_nfe': True,
                    'faturamento_id': str(f.pk),
                    'numero_faturamento': (f.numero_faturamento or '').strip(),
                    'mensagem': (
                        'Status GERADO_NFE sem NF-e vinculada. Use reparar vínculo ou estornar faturamento.'
                    ),
                },
            )
        elif not f.nfe_saida_id:
            inconsistencias.append(
                {
                    'codigo': 'fat_vinculo_orfao',
                    'bloqueia_geracao_nfe': True,
                    'faturamento_id': str(f.pk),
                    'numero_faturamento': (f.numero_faturamento or '').strip(),
                    'mensagem': 'NF-e existe pelo faturamento, mas o vínculo direto está ausente. Reparar vínculo.',
                },
            )

    totais_pedido = calcular_totais_pedido_venda(pedido, itens=itens)
    valor_total_pedido = totais_pedido.valor_total
    valor_pendente = max(Decimal('0'), valor_total_pedido - valor_faturado)

    if totais_pedido.divergente_salvo:
        inconsistencias.append(
            {
                'codigo': 'valor_total_pedido_desatualizado',
                'bloqueia_geracao_nfe': False,
                'mensagem': (
                    f'Valor total salvo no pedido ({totais_pedido.valor_total_salvo}) diverge da soma dos '
                    f'itens ({valor_total_pedido}). Atualize o total do pedido para alinhar o cabeçalho.'
                ),
            },
        )

    if valor_faturado > valor_total_pedido + Decimal('0.01'):
        inconsistencias.append(
            {
                'codigo': 'valor_faturado_excede_pedido',
                'bloqueia_geracao_nfe': True,
                'mensagem': (
                    f'Valor faturado ({valor_faturado}) excede o total do pedido ({valor_total_pedido}). '
                    'Revise faturamentos ou estorne registros inconsistentes.'
                ),
            },
        )

    from apps.comercial.pedido_nfe_historico import (
        montar_historico_nfe_pedido_venda,
        resumo_nfe_fiscal_ativa_pedido,
    )
    from apps.comercial.services.resumo_atendimento_operacional import (
        obter_resumo_atendimento_operacional,
    )

    resumo_operacional_pedido = obter_resumo_atendimento_operacional(pedido)

    historico_nfe = montar_historico_nfe_pedido_venda(pedido)
    resumo_fiscal_ativa = resumo_nfe_fiscal_ativa_pedido(historico_nfe)

    return {
        'pedido_id': pedido.pk,
        'status': pedido.status,
        'pode_faturar': pode,
        'motivo_bloqueio': motivo,
        'total_itens': len(itens_resumo),
        'itens_pendentes': itens_pendentes,
        'itens_parciais': itens_parciais,
        'itens_faturados': itens_faturados,
        'valor_total_pedido': str(_round_money(valor_total_pedido)),
        'valor_total_pedido_salvo': str(totais_pedido.valor_total_salvo),
        'valor_total_recalculado': totais_pedido.divergente_salvo,
        'valor_faturado': str(_round_money(valor_faturado)),
        'valor_pendente': str(_round_money(valor_pendente)),
        'inconsistencias': inconsistencias,
        'tem_inconsistencia_fiscal': bool(inconsistencias),
        'tem_inconsistencia_bloqueante_nfe': any(
            inc.get('bloqueia_geracao_nfe') for inc in inconsistencias
        ),
        'faturamentos_rascunho': rascunhos,
        'faturamentos_nfe': faturamentos_nfe,
        'historico_nfe_saida': historico_nfe,
        **resumo_fiscal_ativa,
        'itens': itens_resumo,
        'resumo_atendimento_operacional': resumo_operacional_pedido,
    }


class CriarFaturamentoPayload(TypedDict, total=False):
    observacao: str
    itens: list[dict[str, Any]]


@transaction.atomic
def criar_faturamento_pedido(
    pedido: PedidoVenda,
    payload: CriarFaturamentoPayload,
    *,
    usuario=None,
) -> dict[str, Any]:
    pedido = PedidoVenda.objects.select_related('cliente').prefetch_related('itens__produto').get(pk=pedido.pk)

    ok, msg = pedido_permite_faturamento(pedido)
    if not ok:
        raise ValueError(msg)

    itens_payload = payload.get('itens') or []
    if not itens_payload:
        raise ValueError('Informe ao menos um item com quantidade a faturar.')

    fat = FaturamentoPedidoVenda.objects.create(
        pedido=pedido,
        status=FaturamentoPedidoVenda.Status.RASCUNHO,
        cliente_snapshot=_snapshot_cliente(pedido),
        observacao=(payload.get('observacao') or '').strip(),
        criado_por=usuario if usuario and getattr(usuario, 'is_authenticated', False) else None,
    )

    itens_map = {it.pk: it for it in pedido.itens.select_related('produto')}
    criados = 0

    for linha in itens_payload:
        item_id = linha.get('item_pedido_id')
        if item_id is None:
            raise ValueError('item_pedido_id é obrigatório em cada linha.')
        item = itens_map.get(int(item_id))
        if item is None:
            raise ValueError(f'Item do pedido {item_id} não encontrado neste pedido.')
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            raise ValueError(f'Item {item_id} está cancelado e não pode ser faturado.')

        qtd = _round_qty(_dec(linha.get('quantidade')))
        if qtd <= 0:
            raise ValueError('Quantidade a faturar deve ser maior que zero.')

        disponivel = quantidade_disponivel_faturar(item)
        if qtd > disponivel:
            raise ValueError(
                f'Quantidade {qtd} excede o saldo disponível ({disponivel}) do item {item_id}.',
            )

        preco, desconto, valor_total = _valor_item_faturamento(item, qtd)
        ItemFaturamentoPedidoVenda.objects.create(
            faturamento=fat,
            item_pedido=item,
            produto=item.produto,
            quantidade=qtd,
            valor_unitario=preco,
            desconto=desconto,
            valor_total=valor_total,
            snapshot_fiscal=item.snapshot_fiscal or {},
            observacao=(linha.get('observacao') or '').strip(),
        )
        criados += 1

    if criados == 0:
        fat.delete()
        raise ValueError('Nenhum item válido para faturamento.')

    recalcular_status_pedido(pedido)

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'itens_criados': criados,
        'mensagens': [MSG_FATURAMENTO_CRIADO],
    }


@transaction.atomic
def confirmar_faturamento_pedido(
    pedido: PedidoVenda,
    faturamento_id: int,
) -> dict[str, Any]:
    pedido = PedidoVenda.objects.prefetch_related('itens').get(pk=pedido.pk)
    try:
        fat = FaturamentoPedidoVenda.objects.select_related('pedido').prefetch_related(
            'itens__item_pedido',
        ).get(pk=faturamento_id, pedido_id=pedido.pk)
    except FaturamentoPedidoVenda.DoesNotExist as exc:
        raise ValueError('Faturamento não encontrado para este pedido.') from exc

    if fat.status != FaturamentoPedidoVenda.Status.RASCUNHO:
        raise ValueError('Somente faturamentos em rascunho podem ser confirmados.')

    ok, msg = pedido_permite_faturamento(pedido)
    if not ok and _status_pedido_normalizado(pedido).upper() not in STATUS_PEDIDO_FATURADO:
        raise ValueError(msg)

    for linha in fat.itens.select_related('item_pedido'):
        item = linha.item_pedido
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            raise ValueError(f'Item {item.pk} cancelado não pode ser confirmado.')

        disponivel = quantidade_pendente_item(item) - quantidade_reservada_rascunho(
            pedido,
            item.pk,
            exclude_faturamento_id=fat.pk,
        )
        if linha.quantidade > disponivel:
            raise ValueError(
                f'Saldo insuficiente no item {item.pk} para confirmar quantidade {linha.quantidade}.',
            )

        item.quantidade_faturada = _round_qty(_dec(item.quantidade_faturada) + linha.quantidade)
        item.save(update_fields=['quantidade_faturada'])
        recalcular_status_item(item)

    from apps.comercial.numbering import gerar_numero_faturamento

    if not (fat.numero_faturamento or '').strip():
        fat.numero_faturamento = gerar_numero_faturamento(fat.criado_em.date() if fat.criado_em else None)

    fat.status = FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE
    fat.save(update_fields=['status', 'numero_faturamento', 'atualizado_em'])

    recalcular_status_pedido(pedido)

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'pedido_status': pedido.status,
        'mensagens': [
            'Faturamento confirmado. Quantidades do pedido atualizadas. NF-e e estoque em etapa posterior.',
        ],
    }


@transaction.atomic
def cancelar_faturamento_pedido(
    pedido: PedidoVenda,
    faturamento_id: int,
) -> dict[str, Any]:
    try:
        fat = FaturamentoPedidoVenda.objects.get(pk=faturamento_id, pedido_id=pedido.pk)
    except FaturamentoPedidoVenda.DoesNotExist as exc:
        raise ValueError('Faturamento não encontrado para este pedido.') from exc

    if fat.status != FaturamentoPedidoVenda.Status.RASCUNHO:
        raise ValueError(
            'Faturamento confirmado não pode ser cancelado nesta fase. Estorno ficará para fase futura.',
        )

    fat.status = FaturamentoPedidoVenda.Status.CANCELADO
    fat.save(update_fields=['status', 'atualizado_em'])
    recalcular_status_pedido(pedido)

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'mensagens': ['Solicitação de faturamento cancelada. Quantidades faturadas do pedido não foram alteradas.'],
    }


def _nfe_permite_estorno_faturamento(nf: NFeSaida) -> tuple[bool, str]:
    from apps.fiscal.nfe_saida_ciclo_vida import avaliar_descarte_nfe_rascunho, nf_esta_descartada_ou_inativa

    if nf_esta_descartada_ou_inativa(nf):
        return True, ''
    return avaliar_descarte_nfe_rascunho(nf)


@transaction.atomic
def estornar_faturamento_pedido(
    pedido: PedidoVenda,
    faturamento_id: int,
    *,
    motivo: str = '',
    usuario=None,
) -> dict[str, Any]:
    """
    Estorna faturamento confirmado (PRONTO_PARA_NFE ou GERADO_NFE) quando seguro.
    Reverte quantidade_faturada dos itens; cancela NF-e rascunho vinculada, se houver.
    """
    pedido = PedidoVenda.objects.prefetch_related('itens').get(pk=pedido.pk)
    try:
        fat = FaturamentoPedidoVenda.objects.prefetch_related('itens__item_pedido').get(
            pk=faturamento_id,
            pedido_id=pedido.pk,
        )
    except FaturamentoPedidoVenda.DoesNotExist as exc:
        raise ValueError('Faturamento não encontrado para este pedido.') from exc

    from apps.fiscal.nfe_saida_ciclo_vida import (
        avaliar_estorno_faturamento,
        descartar_nfe_no_estorno_faturamento,
        nf_esta_descartada_ou_inativa,
        validar_motivo_estorno_ou_descarte,
    )

    motivo = validar_motivo_estorno_ou_descarte(motivo)

    if fat.status == FaturamentoPedidoVenda.Status.RASCUNHO:
        return cancelar_faturamento_pedido(pedido, faturamento_id)

    if fat.status == FaturamentoPedidoVenda.Status.CANCELADO:
        raise ValueError('Faturamento já foi estornado.')

    pode_est, msg_est = avaliar_estorno_faturamento(faturamento=fat)
    if not pode_est:
        raise ValueError(msg_est)

    nf: NFeSaida | None = None
    if fat.nfe_saida_id:
        nf = fat.nfe_saida
    elif fat.status == FaturamentoPedidoVenda.Status.GERADO_NFE:
        nf = NFeSaida.objects.filter(faturamento_pedido_venda_id=fat.pk).order_by('-id').first()
        if nf and not fat.nfe_saida_id:
            fat.nfe_saida = nf
            fat.save(update_fields=['nfe_saida', 'atualizado_em'])

    nf_id_descartada: int | None = None
    if nf and not nf_esta_descartada_ou_inativa(nf):
        descartar_nfe_no_estorno_faturamento(nf, motivo=motivo, usuario=usuario, faturamento=fat)
        nf_id_descartada = nf.pk

    for linha in fat.itens.select_related('item_pedido'):
        item = linha.item_pedido
        if item.status_item == ItemPedidoVenda.StatusItem.CANCELADO:
            continue
        nova_faturada = _round_qty(_dec(item.quantidade_faturada) - _dec(linha.quantidade))
        if nova_faturada < 0:
            raise ValueError(
                f'Inconsistência: quantidade faturada do item {item.pk} ficaria negativa ao estornar.',
            )
        item.quantidade_faturada = nova_faturada
        item.save(update_fields=['quantidade_faturada'])
        recalcular_status_item(item)

    obs = (fat.observacao or '').strip()
    if motivo.strip():
        obs = f'{obs}\n[Estorno] {motivo.strip()}'.strip()

    fat.status = FaturamentoPedidoVenda.Status.CANCELADO
    fat.nfe_saida_id = None
    fat.nfe_saida_gerada_em = None
    fat.observacao = obs
    fat.save(update_fields=['status', 'nfe_saida', 'nfe_saida_gerada_em', 'observacao', 'atualizado_em'])

    recalcular_status_pedido(pedido)

    num_fat = (fat.numero_faturamento or f'#{fat.pk}').strip()
    num_nf = ''
    if nf_id_descartada:
        num_nf = NFeSaida.objects.filter(pk=nf_id_descartada).values_list('numero', flat=True).first() or ''
    linha_hist = (
        f'Faturamento {num_fat} estornado antes da autorização da NF-e'
        f'{" " + num_nf if num_nf else ""}. Pedido reaberto para edição. Motivo: {motivo}'
    )
    base_obs = (pedido.observacoes_internas or '').strip()
    pedido.observacoes_internas = f'{base_obs}\n[{linha_hist}]'.strip() if base_obs else f'[{linha_hist}]'
    pedido.save(update_fields=['observacoes_internas'])

    mensagens = [
        'Faturamento estornado antes da autorização da NF-e. Pedido reaberto para edição.',
        'Nenhum evento foi enviado à SEFAZ.',
    ]
    if nf_id_descartada:
        mensagens.append('NF-e rascunho vinculada marcada como descartada internamente (histórico preservado).')

    return {
        'faturamento_id': fat.pk,
        'pedido_id': pedido.pk,
        'status': fat.status,
        'status_anterior_faturamento': FaturamentoPedidoVenda.Status.GERADO_NFE,
        'pedido_status': pedido.status,
        'nfe_descartada_id': nf_id_descartada,
        'mensagem': mensagens[0],
        'mensagens': mensagens,
    }


@transaction.atomic
def reparar_vinculo_faturamento_nfe(pedido: PedidoVenda, faturamento_id: int) -> dict[str, Any]:
    """Corrige FAT GERADO_NFE órfão (status sem nfe_saida_id) quando NF-e existe pelo FK inverso."""
    try:
        fat = FaturamentoPedidoVenda.objects.get(pk=faturamento_id, pedido_id=pedido.pk)
    except FaturamentoPedidoVenda.DoesNotExist as exc:
        raise ValueError('Faturamento não encontrado para este pedido.') from exc

    if fat.status != FaturamentoPedidoVenda.Status.GERADO_NFE:
        raise ValueError('Reparo de vínculo só se aplica a faturamento com status GERADO_NFE.')

    if fat.nfe_saida_id:
        return {
            'faturamento_id': fat.pk,
            'nfe_saida_id': fat.nfe_saida_id,
            'reparado': False,
            'mensagens': ['Vínculo já consistente.'],
        }

    nf = NFeSaida.objects.filter(faturamento_pedido_venda_id=fat.pk).order_by('-id').first()
    if not nf:
        fat.status = FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE
        fat.save(update_fields=['status', 'atualizado_em'])
        return {
            'faturamento_id': fat.pk,
            'nfe_saida_id': None,
            'reparado': True,
            'mensagens': [
                'Nenhuma NF-e localizada — status do faturamento corrigido para PRONTO_PARA_NFE.',
            ],
        }

    fat.nfe_saida = nf
    fat.nfe_saida_gerada_em = fat.nfe_saida_gerada_em or nf.criado_em
    fat.save(update_fields=['nfe_saida', 'nfe_saida_gerada_em', 'atualizado_em'])
    if not nf.faturamento_pedido_venda_id:
        nf.faturamento_pedido_venda = fat
        nf.save(update_fields=['faturamento_pedido_venda'])

    return {
        'faturamento_id': fat.pk,
        'nfe_saida_id': nf.pk,
        'reparado': True,
        'mensagens': [f'Vínculo reparado com NF-e id={nf.pk}.'],
    }
