"""Fase 1 — conciliação operacional NF-e Entrada (histórica/conferência) × Pedido de Venda.

Somente intenção informativa via AlocacaoAtendimento.
Não movimenta estoque, não baixa PC, não gera financeiro, não altera documento fiscal.

Upsert (mesma origem × destino): a quantidade enviada SUBSTITUI o total da alocação
(não é incremento). Resposta indica 'criado' ou 'atualizado'.

Locks: sempre ItemNFeEntradaHistoricaImportada → ItemPedidoVenda (nessa ordem).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from django.db import transaction
from django.db.models import Sum

from apps.comercial.services.alocacao_atendimento_service import AlocacaoAtendimentoErro, _dec
from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)
from apps.fiscal.models import (
    AlocacaoAtendimento,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaida,
)

TOL = Decimal('0.0005')

ESTADO_SEM_ALOCACAO = 'SEM_ALOCACAO'
ESTADO_PARCIAL = 'PARCIAL'
ESTADO_CONCILIADO = 'CONCILIADO'
ESTADO_DIVERGENTE = 'DIVERGENTE'

AcaoUpsert = Literal['criado', 'atualizado']


def _qty_str(v: Decimal) -> str:
    return str(v.quantize(Decimal('0.001')))


def _norm_unidade(u: str | None) -> str:
    return (u or '').strip().upper()


def obter_item_conferencia_por_historico(
    nf_entrada_historica_item_id: int,
    *,
    for_update: bool = False,
) -> ItemNFeEntradaConferencia:
    qs = ItemNFeEntradaConferencia.objects.all()
    if for_update:
        qs = qs.select_for_update()
    try:
        item = qs.get(item_nfe_historico_id=nf_entrada_historica_item_id)
    except ItemNFeEntradaConferencia.DoesNotExist as exc:
        raise AlocacaoAtendimentoErro(
            'Item de conferência não encontrado para o item da NF-e de entrada histórica. '
            'Conclua a conferência antes de alocar para venda.',
        ) from exc
    return (
        ItemNFeEntradaConferencia.objects.select_related(
            'produto',
            'item_nfe_historico',
            'item_nfe_historico__nf',
            'item_nfe_historico__nf__fornecedor_emitente',
            'conferencia',
            'item_pedido_compra',
        ).get(pk=item.pk)
    )


def obter_item_conferencia(
    item_conferencia_id: int,
    *,
    for_update: bool = False,
) -> ItemNFeEntradaConferencia:
    qs = ItemNFeEntradaConferencia.objects.all()
    if for_update:
        qs = qs.select_for_update()
    try:
        item = qs.get(pk=item_conferencia_id)
    except ItemNFeEntradaConferencia.DoesNotExist as exc:
        raise AlocacaoAtendimentoErro('Item de conferência não encontrado.') from exc
    return (
        ItemNFeEntradaConferencia.objects.select_related(
            'produto',
            'item_nfe_historico',
            'item_nfe_historico__nf',
            'item_nfe_historico__nf__fornecedor_emitente',
            'conferencia',
            'item_pedido_compra',
        ).get(pk=item.pk)
    )


def quantidade_disponivel_entrada(item_conf: ItemNFeEntradaConferencia) -> Decimal:
    """Quantidade interna normalizada: somente quantidade_estoque_calculada."""
    if item_conf.quantidade_estoque_calculada is None:
        raise AlocacaoAtendimentoErro(
            'Quantidade interna da conferência (quantidade_estoque_calculada) está ausente. '
            'Confirme produto/equivalência antes de alocar.',
        )
    q = _dec(item_conf.quantidade_estoque_calculada)
    if q <= 0:
        raise AlocacaoAtendimentoErro(
            'Quantidade interna da conferência (quantidade_estoque_calculada) está zerada. '
            'Confirme produto/equivalência e a quantidade de estoque calculada antes de alocar.',
        )
    return q


def unidade_origem_entrada(item_conf: ItemNFeEntradaConferencia) -> str:
    u = _norm_unidade(item_conf.unidade_estoque_calculada)
    if u:
        return u
    if item_conf.produto_id and item_conf.produto:
        return _norm_unidade(item_conf.produto.unidade)
    return ''


def necessidade_destino_pv(item) -> tuple[Decimal, str, str]:
    """Necessidade canônica do item de PV para conciliação com entrada.

    Ordem (None ≠ zero):
    1) Se ``unidade_estoque_calculada`` do PV estiver preenchida → usa
       ``quantidade_estoque_calculada`` (zero é válido).
    2) Senão, se ``unidade_negociada`` estiver preenchida → usa
       ``quantidade_negociada`` (zero é válido; não cai para ``quantidade``).
    3) Senão → ``quantidade`` (campo obrigatório do item) + unidade do produto.

    Retorna (necessidade, unidade, fonte).
    """
    u_est = _norm_unidade(getattr(item, 'unidade_estoque_calculada', None))
    if u_est:
        return _dec(item.quantidade_estoque_calculada), u_est, 'quantidade_estoque_calculada'

    u_neg = _norm_unidade(getattr(item, 'unidade_negociada', None))
    if u_neg:
        return _dec(item.quantidade_negociada), u_neg, 'quantidade_negociada'

    u_prod = ''
    if getattr(item, 'produto_id', None) and getattr(item, 'produto', None):
        u_prod = _norm_unidade(item.produto.unidade)
    return _dec(item.quantidade), u_prod, 'quantidade'


def garantir_unidades_compativeis(unidade_origem: str, unidade_destino: str) -> None:
    o = _norm_unidade(unidade_origem)
    d = _norm_unidade(unidade_destino)
    if not o or not d:
        raise AlocacaoAtendimentoErro(
            'Não foi possível confirmar equivalência de unidade entre a quantidade '
            'interna da entrada e a necessidade do Pedido de Venda. '
            'Preencha unidade_estoque_calculada na conferência e no item do PV '
            '(ou unidade_negociada / unidade do produto) antes de alocar.',
        )
    if o != d:
        raise AlocacaoAtendimentoErro(
            f'Unidades incompatíveis para conciliação: origem={o}, destino={d}. '
            'Não há conversão automática nesta fase.',
        )


def total_alocado_entrada(
    nf_entrada_historica_item_id: int,
    *,
    excluir_id: int | None = None,
) -> Decimal:
    qs = AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=nf_entrada_historica_item_id)
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return qs.aggregate(s=Sum('quantidade_necessaria'))['s'] or Decimal('0')


def total_alocado_destino_pv(
    pedido_venda_item_id: int,
    *,
    excluir_id: int | None = None,
) -> Decimal:
    qs = AlocacaoAtendimento.objects.filter(pedido_venda_item_id=pedido_venda_item_id)
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return qs.aggregate(s=Sum('quantidade_necessaria'))['s'] or Decimal('0')


def estado_operacional_entrada(
    *,
    quantidade_disponivel: Decimal,
    total_alocado: Decimal,
) -> str:
    """Estados calculados. DIVERGENTE só com inconsistência real (ex.: alocado > disponível).

    Estoque não aplicado NÃO gera DIVERGENTE.
    """
    if total_alocado < 0:
        return ESTADO_DIVERGENTE
    if quantidade_disponivel > 0 and total_alocado > quantidade_disponivel + TOL:
        return ESTADO_DIVERGENTE
    if total_alocado <= TOL:
        return ESTADO_SEM_ALOCACAO
    if quantidade_disponivel > 0 and total_alocado + TOL >= quantidade_disponivel:
        return ESTADO_CONCILIADO
    if quantidade_disponivel <= 0 and total_alocado > TOL:
        return ESTADO_DIVERGENTE
    return ESTADO_PARCIAL


def listar_documentos_relacionados_pv_item(pedido_venda_item) -> dict[str, Any]:
    """Informação de Fat/NF-e ligados ao item — sem escolher FK ambígua."""
    from apps.comercial.models import ItemFaturamentoPedidoVenda

    fat_itens = list(
        ItemFaturamentoPedidoVenda.objects.filter(item_pedido_id=pedido_venda_item.pk)
        .select_related('faturamento')
        .order_by('id'),
    )
    faturamentos = []
    nfes: list[dict[str, Any]] = []
    for fat in fat_itens:
        faturamentos.append(
            {
                'faturamento_item_id': fat.pk,
                'faturamento_id': fat.faturamento_id,
                'numero': fat.faturamento.numero_faturamento if fat.faturamento_id else '',
            },
        )
        for nf_item in ItemNFeSaida.objects.filter(item_faturamento_pedido_id=fat.pk).select_related('nf').order_by('id'):
            nfes.append(
                {
                    'item_nf_saida_id': nf_item.pk,
                    'nfe_saida_id': nf_item.nf_id,
                    'numero': nf_item.nf.numero if nf_item.nf_id else '',
                    'faturamento_item_id': fat.pk,
                },
            )
    return {
        'faturamentos': faturamentos,
        'nfes_saida': nfes,
        'cadeia_ambigua': len(faturamentos) > 1 or len(nfes) > 1,
    }


def resolver_fks_cadeia_para_persistir(
    pedido_venda_item,
    *,
    faturamento_item=None,
    item_nf_saida=None,
) -> tuple[Any | None, Any | None]:
    """Valida FKs explícitas; só deriva FK quando há exatamente um documento na cadeia.

    Com múltiplos faturamentos/NF-e: não persiste FK ambígua (retorna None).
    """
    from apps.comercial.models import ItemFaturamentoPedidoVenda

    docs = listar_documentos_relacionados_pv_item(pedido_venda_item)

    fat_obj = None
    if faturamento_item is not None:
        fat_id = faturamento_item.pk if hasattr(faturamento_item, 'pk') else int(faturamento_item)
        try:
            fat_obj = (
                faturamento_item
                if hasattr(faturamento_item, 'item_pedido_id')
                else ItemFaturamentoPedidoVenda.objects.select_related('faturamento').get(pk=fat_id)
            )
        except ItemFaturamentoPedidoVenda.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item de faturamento não encontrado.') from exc
        if fat_obj.item_pedido_id != pedido_venda_item.pk:
            raise AlocacaoAtendimentoErro(
                'O item de faturamento não pertence ao item do Pedido de Venda informado (cadeia incompatível).',
            )

    nf_obj = None
    if item_nf_saida is not None:
        nf_id = item_nf_saida.pk if hasattr(item_nf_saida, 'pk') else int(item_nf_saida)
        try:
            nf_obj = (
                item_nf_saida
                if hasattr(item_nf_saida, 'item_faturamento_pedido_id')
                else ItemNFeSaida.objects.select_related('nf', 'item_faturamento_pedido').get(pk=nf_id)
            )
        except ItemNFeSaida.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item da NF-e de saída não encontrado.') from exc
        fat_ref_id = nf_obj.item_faturamento_pedido_id
        if not fat_ref_id:
            raise AlocacaoAtendimentoErro(
                'O item da NF-e de saída não está vinculado a faturamento da cadeia do Pedido de Venda.',
            )
        try:
            fat_via_nf = ItemFaturamentoPedidoVenda.objects.get(pk=fat_ref_id)
        except ItemFaturamentoPedidoVenda.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro(
                'O item da NF-e de saída aponta para faturamento inexistente.',
            ) from exc
        if fat_via_nf.item_pedido_id != pedido_venda_item.pk:
            raise AlocacaoAtendimentoErro(
                'O item da NF-e de saída não pertence à cadeia do Pedido de Venda informado.',
            )
        if fat_obj is not None and fat_obj.pk != fat_via_nf.pk:
            raise AlocacaoAtendimentoErro(
                'O item da NF-e de saída não pertence ao faturamento informado (cadeia incompatível).',
            )
        if fat_obj is None:
            fat_obj = fat_via_nf

    if faturamento_item is None and item_nf_saida is None:
        # Derivação segura: só quando há exatamente um de cada (ou fat único sem NF).
        if len(docs['faturamentos']) == 1:
            fat_id = docs['faturamentos'][0]['faturamento_item_id']
            fat_obj = ItemFaturamentoPedidoVenda.objects.select_related('faturamento').get(pk=fat_id)
            nfs_do_fat = [n for n in docs['nfes_saida'] if n['faturamento_item_id'] == fat_id]
            if len(nfs_do_fat) == 1:
                nf_obj = ItemNFeSaida.objects.select_related('nf').get(pk=nfs_do_fat[0]['item_nf_saida_id'])
            else:
                nf_obj = None  # 0 ou muitos — não persiste NF ambígua
        else:
            fat_obj = None
            nf_obj = None

    return fat_obj, nf_obj


# Alias compatível com imports anteriores / CRUD genérico
def validar_cadeia_comercial(
    *,
    pedido_venda_item,
    faturamento_item=None,
    item_nf_saida=None,
) -> tuple[Any | None, Any | None]:
    return resolver_fks_cadeia_para_persistir(
        pedido_venda_item,
        faturamento_item=faturamento_item,
        item_nf_saida=item_nf_saida,
    )


def validar_limites_origem_destino(
    *,
    nf_entrada_historica_item_id: int,
    pedido_venda_item_id: int,
    quantidade: Decimal,
    excluir_id: int | None = None,
    item_conf: ItemNFeEntradaConferencia | None = None,
    item_pv=None,
) -> None:
    if quantidade is None or quantidade == '':
        raise AlocacaoAtendimentoErro('Quantidade deve ser maior que zero.')
    if quantidade <= 0:
        raise AlocacaoAtendimentoErro('Quantidade deve ser maior que zero.')

    conf = item_conf or obter_item_conferencia_por_historico(nf_entrada_historica_item_id)
    disponivel = quantidade_disponivel_entrada(conf)
    u_origem = unidade_origem_entrada(conf)

    from apps.comercial.models import ItemPedidoVenda

    if item_pv is None:
        try:
            item_pv = ItemPedidoVenda.objects.select_related('produto').get(pk=pedido_venda_item_id)
        except ItemPedidoVenda.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item do pedido de venda não encontrado.') from exc

    necessidade, u_destino, _fonte = necessidade_destino_pv(item_pv)
    garantir_unidades_compativeis(u_origem, u_destino)

    alocado_origem = total_alocado_entrada(nf_entrada_historica_item_id, excluir_id=excluir_id)
    if alocado_origem + quantidade > disponivel + TOL:
        raise AlocacaoAtendimentoErro(
            f'A soma das alocações da entrada ({_qty_str(alocado_origem + quantidade)}) '
            f'ultrapassa a quantidade disponível ({_qty_str(disponivel)}).',
        )

    alocado_destino = total_alocado_destino_pv(pedido_venda_item_id, excluir_id=excluir_id)
    if alocado_destino + quantidade > necessidade + TOL:
        raise AlocacaoAtendimentoErro(
            f'A soma das alocações do destino ({_qty_str(alocado_destino + quantidade)}) '
            f'ultrapassa a necessidade do item no PV ({_qty_str(necessidade)}).',
        )


def encontrar_alocacao_duplicada(
    *,
    nf_entrada_historica_item_id: int,
    pedido_venda_item_id: int,
    excluir_id: int | None = None,
) -> AlocacaoAtendimento | None:
    qs = AlocacaoAtendimento.objects.filter(
        nf_entrada_historica_item_id=nf_entrada_historica_item_id,
        pedido_venda_item_id=pedido_venda_item_id,
    )
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return qs.order_by('id').first()


def _bloquear_origem_destino(*, hist_id: int, pvi_id: int) -> None:
    """Ordem fixa anti-deadlock: entrada histórica → item PV."""
    from apps.comercial.models import ItemPedidoVenda

    ItemNFeEntradaHistoricaImportada.objects.select_for_update().get(pk=hist_id)
    ItemPedidoVenda.objects.select_for_update().get(pk=pvi_id)


def montar_resumo_entrada_venda(item_conf: ItemNFeEntradaConferencia) -> dict[str, Any]:
    hist_id = item_conf.item_nfe_historico_id
    disponivel_raw = item_conf.quantidade_estoque_calculada
    disponivel = _dec(disponivel_raw) if disponivel_raw is not None else Decimal('0')
    alocado = total_alocado_entrada(hist_id) if hist_id else Decimal('0')
    saldo = max(disponivel - alocado, Decimal('0'))
    estado = estado_operacional_entrada(quantidade_disponivel=disponivel, total_alocado=alocado)

    estoque_aplicado = bool(item_conf.estoque_aplicado_em) or _dec(item_conf.quantidade_estoque_aplicada) > 0
    aviso_estoque = None
    if not estoque_aplicado:
        aviso_estoque = (
            'Estoque físico ainda não foi aplicado nesta linha. '
            'A alocação operacional é permitida e não movimenta saldo nem baixa Pedido de Compra.'
        )

    alocacoes = (
        AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=hist_id)
        .select_related(
            'pedido_venda_item',
            'pedido_venda_item__pedido',
            'pedido_venda_item__pedido__cliente',
            'pedido_venda_item__produto',
            'faturamento_item',
            'faturamento_item__faturamento',
            'item_nf_saida',
            'item_nf_saida__nf',
            'produto',
        )
        .order_by('id')
    )
    lista = []
    for a in alocacoes:
        pvi = a.pedido_venda_item
        pv = pvi.pedido if pvi else None
        cliente = ''
        if pv and pv.cliente_id and pv.cliente:
            cliente = (pv.cliente.nome_fantasia or pv.cliente.razao_social or '').strip()
        fat = a.faturamento_item
        nf_item = a.item_nf_saida
        necessidade = Decimal('0')
        alocado_dest = Decimal('0')
        docs: dict[str, Any] = {'faturamentos': [], 'nfes_saida': [], 'cadeia_ambigua': False}
        if pvi:
            necessidade, _, _ = necessidade_destino_pv(pvi)
            alocado_dest = total_alocado_destino_pv(pvi.pk)
            docs = listar_documentos_relacionados_pv_item(pvi)
        lista.append(
            {
                'id': a.pk,
                'pedido_venda_item_id': a.pedido_venda_item_id,
                'pedido_venda_id': pv.pk if pv else None,
                'pedido_venda_numero': pv.numero if pv else '',
                'cliente_nome': cliente,
                'produto_id': a.produto_id,
                'produto_codigo': a.produto.codigo_completo if a.produto_id else '',
                'produto_nome': a.produto.descricao if a.produto_id else '',
                'quantidade_alocada': _qty_str(_dec(a.quantidade_necessaria)),
                'necessidade_destino': _qty_str(necessidade),
                'total_alocado_destino': _qty_str(alocado_dest),
                'saldo_destino': _qty_str(max(necessidade - alocado_dest, Decimal('0'))),
                'faturamento_id': fat.faturamento_id if fat else None,
                'faturamento_numero': fat.faturamento.numero_faturamento if fat and fat.faturamento_id else None,
                'nfe_saida_id': nf_item.nf_id if nf_item else None,
                'nfe_saida_numero': nf_item.nf.numero if nf_item and nf_item.nf_id else None,
                'documentos_relacionados': docs,
                'criado_em': a.criado_em.isoformat() if a.criado_em else None,
                'atualizado_em': a.atualizado_em.isoformat() if a.atualizado_em else None,
            },
        )

    return {
        'item_conferencia_id': item_conf.pk,
        'nf_entrada_historica_item_id': hist_id,
        'produto_id': item_conf.produto_id,
        'produto_codigo': item_conf.produto.codigo_completo if item_conf.produto_id else '',
        'produto_nome': item_conf.produto.descricao if item_conf.produto_id else '',
        'unidade_estoque_calculada': item_conf.unidade_estoque_calculada or '',
        'quantidade_disponivel': _qty_str(disponivel),
        'total_alocado': _qty_str(alocado),
        'saldo_entrada': _qty_str(saldo),
        'estado_operacional': estado,
        'estoque_aplicado': estoque_aplicado,
        'aviso_estoque': aviso_estoque,
        'alocacoes': lista,
        'aviso_operacional': (
            'Alocação operacional e informativa: não movimenta estoque, '
            'não baixa Pedido de Compra, não gera financeiro e não altera NF-e.'
        ),
    }


def montar_opcao_pedido_venda_item(item, *, excluir_alocacao_id: int | None = None) -> dict[str, Any]:
    necessidade, unidade, fonte = necessidade_destino_pv(item)
    alocado = total_alocado_destino_pv(item.pk, excluir_id=excluir_alocacao_id)
    saldo = max(necessidade - alocado, Decimal('0'))
    docs = listar_documentos_relacionados_pv_item(item)
    pv = item.pedido
    cliente = ''
    if pv and pv.cliente_id and pv.cliente:
        cliente = (pv.cliente.nome_fantasia or pv.cliente.razao_social or '').strip()
    fat_num = docs['faturamentos'][0]['numero'] if len(docs['faturamentos']) == 1 else None
    nf_num = docs['nfes_saida'][0]['numero'] if len(docs['nfes_saida']) == 1 else None
    return {
        'id': item.pk,
        'pedido_venda_id': pv.pk if pv else None,
        'pedido_venda_numero': pv.numero if pv else '',
        'cliente_nome': cliente,
        'produto_id': item.produto_id,
        'produto_codigo': item.produto.codigo_completo if item.produto_id else '',
        'produto_nome': item.produto.descricao if item.produto_id else '',
        'quantidade_necessaria': _qty_str(necessidade),
        'unidade_necessidade': unidade,
        'fonte_necessidade': fonte,
        'quantidade_ja_alocada': _qty_str(alocado),
        'saldo_destino': _qty_str(saldo),
        'faturamento_id': docs['faturamentos'][0]['faturamento_id'] if len(docs['faturamentos']) == 1 else None,
        'faturamento_numero': fat_num,
        'nfe_saida_id': docs['nfes_saida'][0]['nfe_saida_id'] if len(docs['nfes_saida']) == 1 else None,
        'nfe_saida_numero': nf_num,
        'documentos_relacionados': docs,
        'label': (
            f'{pv.numero if pv else "PV"} — {cliente or "—"} — '
            f'{item.produto.codigo_completo if item.produto_id else "?"} '
            f'(saldo {_qty_str(saldo)} {unidade})'
        ),
    }


def buscar_pedidos_venda_itens_opcoes(params: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.comercial.models import ItemPedidoVenda

    qs = ItemPedidoVenda.objects.select_related(
        'pedido',
        'pedido__cliente',
        'produto',
    ).order_by('-pedido__data', '-id')
    term = (params.get('search') or params.get('q') or '').strip()
    if term:
        from django.db.models import Q

        qs = qs.filter(
            Q(pedido__numero__icontains=term)
            | Q(pedido__cliente__razao_social__icontains=term)
            | Q(pedido__cliente__nome_fantasia__icontains=term)
            | Q(produto__codigo_completo__icontains=term)
            | Q(produto__descricao__icontains=term),
        )
    if params.get('produto_id'):
        try:
            qs = qs.filter(produto_id=int(params['produto_id']))
        except (TypeError, ValueError):
            pass
    try:
        lim = max(1, min(int(params.get('limit') or 20), 50))
    except (TypeError, ValueError):
        lim = 20
    return [montar_opcao_pedido_venda_item(it) for it in qs[:lim]]


def _montar_dados_alocacao(
    *,
    item_conf: ItemNFeEntradaConferencia,
    pvi,
    qtd: Decimal,
    fat_obj,
    nf_obj,
    observacao_operacional: str,
) -> dict[str, Any]:
    dados = {
        'pedido_venda_item': pvi,
        'produto': item_conf.produto,
        'quantidade_necessaria': qtd,
        'quantidade_atendida': qtd,
        'quantidade_pendente': Decimal('0'),
        'tipo_atendimento': TipoAtendimentoItem.ENTRADA_CONCILIADA,
        'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
        'origem_fisica': OrigemFisica.ESTOQUE_PROPRIO,
        'destino_fisico': DestinoFisico.CLIENTE,
        'nf_entrada_historica_item': item_conf.item_nfe_historico,
        'faturamento_item': fat_obj,
        'item_nf_saida': nf_obj,
        'observacao_operacional': (observacao_operacional or '').strip(),
    }
    if item_conf.item_pedido_compra_id:
        dados['pedido_compra_item'] = item_conf.item_pedido_compra
    if item_conf.item_nfe_historico and item_conf.item_nfe_historico.nf_id:
        nf_hist = item_conf.item_nfe_historico.nf
        if getattr(nf_hist, 'fornecedor_emitente_id', None):
            dados['fornecedor'] = nf_hist.fornecedor_emitente
    return dados


@transaction.atomic
def alocar_entrada_para_venda(
    *,
    item_conferencia_id: int | None = None,
    nf_entrada_historica_item_id: int | None = None,
    pedido_venda_item_id: int,
    quantidade: Decimal | str | float | int,
    observacao_operacional: str = '',
    faturamento_item_id: int | None = None,
    item_nf_saida_id: int | None = None,
) -> tuple[AlocacaoAtendimento, AcaoUpsert]:
    """Cria ou atualiza alocação entrada×PV.

    Semântica do upsert: a quantidade enviada é o valor TOTAL final da alocação
    (substitui; não soma à anterior).
    """
    from apps.comercial.models import ItemPedidoVenda

    if quantidade is None or quantidade == '':
        raise AlocacaoAtendimentoErro('Quantidade deve ser maior que zero.')
    qtd = _dec(quantidade)
    if qtd <= 0:
        raise AlocacaoAtendimentoErro('Quantidade deve ser maior que zero.')

    # Resolve hist_id antes dos locks (sem for_update ainda).
    if item_conferencia_id:
        item_conf_peek = obter_item_conferencia(int(item_conferencia_id), for_update=False)
        hist_id = item_conf_peek.item_nfe_historico_id
    elif nf_entrada_historica_item_id:
        hist_id = int(nf_entrada_historica_item_id)
    else:
        raise AlocacaoAtendimentoErro('Informe item_conferencia_id ou nf_entrada_historica_item_id.')

    _bloquear_origem_destino(hist_id=hist_id, pvi_id=int(pedido_venda_item_id))
    item_conf = obter_item_conferencia_por_historico(hist_id, for_update=True)

    if not item_conf.produto_id:
        raise AlocacaoAtendimentoErro(
            'Vincule o produto interno na conferência antes de alocar para venda.',
        )

    pvi = ItemPedidoVenda.objects.select_related('pedido', 'pedido__cliente', 'produto').get(
        pk=pedido_venda_item_id,
    )

    fat_in = None
    nf_in = None
    if faturamento_item_id:
        from apps.comercial.models import ItemFaturamentoPedidoVenda

        try:
            fat_in = ItemFaturamentoPedidoVenda.objects.get(pk=faturamento_item_id)
        except ItemFaturamentoPedidoVenda.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item de faturamento não encontrado.') from exc
    if item_nf_saida_id:
        try:
            nf_in = ItemNFeSaida.objects.get(pk=item_nf_saida_id)
        except ItemNFeSaida.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item da NF-e de saída não encontrado.') from exc

    fat_obj, nf_obj = resolver_fks_cadeia_para_persistir(
        pvi,
        faturamento_item=fat_in,
        item_nf_saida=nf_in,
    )

    existente = encontrar_alocacao_duplicada(
        nf_entrada_historica_item_id=hist_id,
        pedido_venda_item_id=pvi.pk,
    )
    if existente:
        existente = AlocacaoAtendimento.objects.select_for_update().get(pk=existente.pk)
    excluir_id = existente.pk if existente else None

    validar_limites_origem_destino(
        nf_entrada_historica_item_id=hist_id,
        pedido_venda_item_id=pvi.pk,
        quantidade=qtd,
        excluir_id=excluir_id,
        item_conf=item_conf,
        item_pv=pvi,
    )

    from apps.comercial.services.alocacao_atendimento_vinculos import validar_vinculos_alocacao

    dados = _montar_dados_alocacao(
        item_conf=item_conf,
        pvi=pvi,
        qtd=qtd,
        fat_obj=fat_obj,
        nf_obj=nf_obj,
        observacao_operacional=observacao_operacional,
    )
    validar_vinculos_alocacao(dados)

    if existente:
        for k, v in dados.items():
            setattr(existente, k, v)
        existente.save()
        return existente, 'atualizado'

    return AlocacaoAtendimento.objects.create(**dados), 'criado'


@transaction.atomic
def atualizar_quantidade_alocacao_entrada_venda(
    alocacao: AlocacaoAtendimento,
    *,
    quantidade: Decimal | str | float | int,
) -> AlocacaoAtendimento:
    if quantidade is None or quantidade == '':
        raise AlocacaoAtendimentoErro('Quantidade deve ser maior que zero.')
    qtd = _dec(quantidade)
    if qtd <= 0:
        raise AlocacaoAtendimentoErro('Quantidade deve ser maior que zero.')
    if not alocacao.nf_entrada_historica_item_id or not alocacao.pedido_venda_item_id:
        raise AlocacaoAtendimentoErro(
            'Esta alocação não possui origem de entrada histórica e destino de PV para conciliação.',
        )

    hist_id = alocacao.nf_entrada_historica_item_id
    pvi_id = alocacao.pedido_venda_item_id
    _bloquear_origem_destino(hist_id=hist_id, pvi_id=pvi_id)
    aloc = AlocacaoAtendimento.objects.select_for_update().get(pk=alocacao.pk)
    item_conf = obter_item_conferencia_por_historico(hist_id, for_update=True)
    from apps.comercial.models import ItemPedidoVenda

    pvi = ItemPedidoVenda.objects.select_related('produto').get(pk=pvi_id)

    validar_limites_origem_destino(
        nf_entrada_historica_item_id=hist_id,
        pedido_venda_item_id=pvi_id,
        quantidade=qtd,
        excluir_id=aloc.pk,
        item_conf=item_conf,
        item_pv=pvi,
    )
    aloc.quantidade_necessaria = qtd
    aloc.quantidade_atendida = qtd
    aloc.quantidade_pendente = Decimal('0')
    aloc.save(update_fields=['quantidade_necessaria', 'quantidade_atendida', 'quantidade_pendente', 'atualizado_em'])
    return aloc


@transaction.atomic
def desvincular_alocacao_entrada_venda(alocacao: AlocacaoAtendimento) -> None:
    """Remove apenas o vínculo operacional. Sem efeito em estoque/PC/financeiro/fiscal."""
    hist_id = alocacao.nf_entrada_historica_item_id
    pvi_id = alocacao.pedido_venda_item_id
    if hist_id and pvi_id:
        _bloquear_origem_destino(hist_id=hist_id, pvi_id=pvi_id)
    aloc = AlocacaoAtendimento.objects.select_for_update().get(pk=alocacao.pk)
    aloc.delete()


def eh_alocacao_entrada_venda(dados: dict[str, Any] | None = None, alocacao: AlocacaoAtendimento | None = None) -> bool:
    """True quando há origem histórica e destino PV (fluxo Fase 1)."""
    hist = None
    pvi = None
    if dados:
        hist = dados.get('nf_entrada_historica_item')
        pvi = dados.get('pedido_venda_item')
    if alocacao:
        if hist is None:
            hist = alocacao.nf_entrada_historica_item_id
        if pvi is None:
            pvi = alocacao.pedido_venda_item_id
    hist_id = hist.pk if hasattr(hist, 'pk') else hist
    pvi_id = pvi.pk if hasattr(pvi, 'pk') else pvi
    return bool(hist_id and pvi_id)
