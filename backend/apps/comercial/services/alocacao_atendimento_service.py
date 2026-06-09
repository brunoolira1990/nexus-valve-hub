"""ERP 4.0.12 — gestão operacional de AlocacaoAtendimento (sem estoque/financeiro/expedição)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models, transaction
from django.db.models import Q, QuerySet, Sum

from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
    resolver_origem_destino_por_tipo,
    resolver_tipo_atendimento_padrao,
)
from apps.fiscal.models import AlocacaoAtendimento


class AlocacaoAtendimentoErro(ValueError):
    pass


def _dec(v: Any) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    d = Decimal(str(v))
    if d < 0:
        raise AlocacaoAtendimentoErro('Quantidades não podem ser negativas.')
    return d


def _quantidade_item_pv(item) -> Decimal:
    from apps.comercial.faturamento_pedido_venda import quantidade_pedida_item

    return quantidade_pedida_item(item)


def validar_quantidades_alocacao(
    *,
    pedido_venda_item_id: int | None,
    quantidade_necessaria: Decimal,
    quantidade_atendida: Decimal,
    quantidade_pendente: Decimal,
    excluir_id: int | None = None,
) -> None:
    if quantidade_necessaria < 0 or quantidade_atendida < 0 or quantidade_pendente < 0:
        raise AlocacaoAtendimentoErro('Quantidades não podem ser negativas.')

    soma_ap = quantidade_atendida + quantidade_pendente
    if soma_ap > quantidade_necessaria + Decimal('0.0005'):
        raise AlocacaoAtendimentoErro(
            'Quantidade atendida + pendente não pode exceder a quantidade necessária desta alocação.',
        )

    if not pedido_venda_item_id:
        return

    from apps.comercial.models import ItemPedidoVenda

    pvi = pedido_venda_item_id
    try:
        item = ItemPedidoVenda.objects.get(pk=pvi)
    except ItemPedidoVenda.DoesNotExist as exc:
        raise AlocacaoAtendimentoErro('Item do pedido de venda não encontrado.') from exc

    qtd_pv = _quantidade_item_pv(item)
    qs = AlocacaoAtendimento.objects.filter(pedido_venda_item_id=item.pk)
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    total_outras = qs.aggregate(s=Sum('quantidade_necessaria'))['s'] or Decimal('0')
    if total_outras + quantidade_necessaria > qtd_pv + Decimal('0.0005'):
        raise AlocacaoAtendimentoErro(
            f'A soma das alocações ({total_outras + quantidade_necessaria}) '
            f'ultrapassa a quantidade do item no PV ({qtd_pv}).',
        )


def _aplicar_sugestao_tipo(dados: dict[str, Any]) -> None:
    tipo = resolver_tipo_atendimento_padrao(tipo_atendimento=dados.get('tipo_atendimento'))
    dados['tipo_atendimento'] = tipo
    if not dados.get('origem_fisica') or dados.get('origem_fisica') == OrigemFisica.NAO_DEFINIDA:
        origem, destino, status = resolver_origem_destino_por_tipo(tipo)
        dados.setdefault('origem_fisica', origem)
        dados.setdefault('destino_fisico', destino)
        if dados.get('status_entrada_fiscal') in (None, '', StatusEntradaFiscal.NAO_APLICAVEL):
            dados.setdefault('status_entrada_fiscal', status)


def _normalizar_payload(dados: dict[str, Any], *, parcial: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}
    campos_dec = ('quantidade_necessaria', 'quantidade_atendida', 'quantidade_pendente')
    for k, v in dados.items():
        if k in campos_dec and v is not None:
            out[k] = _dec(v)
        elif v is not None:
            out[k] = v
    if not parcial or 'tipo_atendimento' in out:
        _aplicar_sugestao_tipo(out if not parcial else {**dados, **out})
    return out


@transaction.atomic
def criar_alocacao_atendimento(dados: dict[str, Any]) -> AlocacaoAtendimento:
    if not dados.get('produto'):
        raise AlocacaoAtendimentoErro('Informe o produto.')
    pvi = dados.get('pedido_venda_item')
    pvi_id = pvi.pk if pvi else None
    if not pvi_id and not dados.get('faturamento_item') and not dados.get('item_nf_saida'):
        raise AlocacaoAtendimentoErro(
            'Informe pedido_venda_item, faturamento_item ou item_nf_saida para vincular a alocação.',
        )

    q_nec = _dec(dados.get('quantidade_necessaria', 0))
    q_at = _dec(dados.get('quantidade_atendida', 0))
    q_pen = dados.get('quantidade_pendente')
    q_pen = _dec(q_pen) if q_pen is not None else max(q_nec - q_at, Decimal('0'))
    dados['quantidade_pendente'] = q_pen

    tipo = resolver_tipo_atendimento_padrao(tipo_atendimento=dados.get('tipo_atendimento'))
    dados['tipo_atendimento'] = tipo
    if not dados.get('origem_fisica') or dados.get('origem_fisica') == OrigemFisica.NAO_DEFINIDA:
        origem, destino, status = resolver_origem_destino_por_tipo(tipo)
        dados.setdefault('origem_fisica', origem)
        dados.setdefault('destino_fisico', destino)
        if dados.get('status_entrada_fiscal') in (None, '', StatusEntradaFiscal.NAO_APLICAVEL):
            dados.setdefault('status_entrada_fiscal', status)

    validar_quantidades_alocacao(
        pedido_venda_item_id=pvi_id,
        quantidade_necessaria=q_nec,
        quantidade_atendida=q_at,
        quantidade_pendente=q_pen,
    )
    from apps.comercial.services.alocacao_atendimento_vinculos import validar_vinculos_alocacao

    validar_vinculos_alocacao(dados)

    return AlocacaoAtendimento.objects.create(**dados)


@transaction.atomic
def atualizar_alocacao_atendimento(alocacao: AlocacaoAtendimento, dados: dict[str, Any]) -> AlocacaoAtendimento:
    payload = _normalizar_payload(dados, parcial=True)
    for k, v in payload.items():
        if hasattr(alocacao, k):
            setattr(alocacao, k, v)

    q_nec = _dec(alocacao.quantidade_necessaria)
    q_at = _dec(alocacao.quantidade_atendida)
    q_pen = _dec(alocacao.quantidade_pendente)
    validar_quantidades_alocacao(
        pedido_venda_item_id=alocacao.pedido_venda_item_id,
        quantidade_necessaria=q_nec,
        quantidade_atendida=q_at,
        quantidade_pendente=q_pen,
        excluir_id=alocacao.pk,
    )
    from apps.comercial.services.alocacao_atendimento_vinculos import validar_vinculos_alocacao

    validar_vinculos_alocacao(payload, alocacao=alocacao)
    alocacao.save()
    return alocacao


@transaction.atomic
def excluir_alocacao_atendimento(alocacao: AlocacaoAtendimento) -> None:
    alocacao.delete()


def _campos_model(payload: dict[str, Any]) -> dict[str, Any]:
    fk_map = {
        'pedido_venda_item': 'pedido_venda_item_id',
        'faturamento_item': 'faturamento_item_id',
        'produto': 'produto_id',
        'pedido_compra_item': 'pedido_compra_item_id',
        'nf_entrada_item': 'nf_entrada_item_id',
        'nf_entrada_historica_item': 'nf_entrada_historica_item_id',
        'cte_historico_importado': 'cte_historico_importado_id',
        'item_nf_saida': 'item_nf_saida_id',
        'fornecedor': 'fornecedor_id',
    }
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if k.endswith('_id'):
            out[k] = v
        elif k in fk_map:
            out[fk_map[k]] = v
        elif hasattr(AlocacaoAtendimento, k):
            out[k] = v
    return out


def queryset_base() -> QuerySet:
    return AlocacaoAtendimento.objects.select_related(
        'produto',
        'pedido_venda_item',
        'pedido_venda_item__pedido',
        'pedido_venda_item__produto',
        'faturamento_item',
        'faturamento_item__faturamento',
        'item_nf_saida',
        'item_nf_saida__nf',
        'fornecedor',
        'pedido_compra_item',
        'pedido_compra_item__pedido',
        'pedido_compra_item__produto',
        'nf_entrada_item',
        'nf_entrada_item__nf',
        'nf_entrada_item__produto',
        'nf_entrada_historica_item',
        'nf_entrada_historica_item__nf',
        'nf_entrada_historica_item__nf__conferencia',
        'nf_entrada_historica_item__item_conferencia',
        'nf_entrada_historica_item__item_conferencia__produto',
        'cte_historico_importado',
        'cte_historico_importado__transportadora',
    )


def filtrar_alocacoes(params: dict[str, Any]) -> QuerySet:
    qs = queryset_base()
    if params.get('pedido_venda'):
        qs = qs.filter(pedido_venda_item__pedido_id=params['pedido_venda'])
    if params.get('pedido_venda_item'):
        qs = qs.filter(pedido_venda_item_id=params['pedido_venda_item'])
    if params.get('faturamento'):
        fid = params['faturamento']
        qs = qs.filter(
            Q(faturamento_item__faturamento_id=fid)
            | Q(pedido_venda_item__pedido__faturamentos__id=fid),
        ).distinct()
    if params.get('nfe_saida'):
        nid = params['nfe_saida']
        qs = qs.filter(
            Q(item_nf_saida__nf_id=nid)
            | Q(pedido_venda_item__pedido__nf_saidas__id=nid),
        ).distinct()
    if params.get('produto'):
        qs = qs.filter(produto_id=params['produto'])
    if params.get('fornecedor'):
        qs = qs.filter(fornecedor_id=params['fornecedor'])
    if params.get('tipo_atendimento'):
        qs = qs.filter(tipo_atendimento=params['tipo_atendimento'])
    if params.get('status_entrada_fiscal'):
        qs = qs.filter(status_entrada_fiscal=params['status_entrada_fiscal'])
    if params.get('origem_fisica'):
        qs = qs.filter(origem_fisica=params['origem_fisica'])
    if params.get('destino_fisico'):
        qs = qs.filter(destino_fisico=params['destino_fisico'])
    return qs


def listar_alocacoes_por_pedido_venda(pedido_id: int) -> QuerySet:
    return filtrar_alocacoes({'pedido_venda': pedido_id})


def listar_alocacoes_por_faturamento(faturamento_id: int) -> QuerySet:
    return filtrar_alocacoes({'faturamento': faturamento_id})


def listar_alocacoes_por_nfe_saida(nfe_id: int) -> QuerySet:
    return filtrar_alocacoes({'nfe_saida': nfe_id})


def obter_resumo_alocacoes_item(pedido_venda_item_id: int) -> dict[str, Any]:
    qs = filtrar_alocacoes({'pedido_venda_item': pedido_venda_item_id})
    total_nec = qs.aggregate(s=Sum('quantidade_necessaria'))['s'] or Decimal('0')
    total_at = qs.aggregate(s=Sum('quantidade_atendida'))['s'] or Decimal('0')
    total_pen = qs.aggregate(s=Sum('quantidade_pendente'))['s'] or Decimal('0')
    return {
        'quantidade_alocacoes': qs.count(),
        'quantidade_necessaria_total': str(total_nec),
        'quantidade_atendida_total': str(total_at),
        'quantidade_pendente_total': str(total_pen),
    }


def recalcular_resumo_atendimento_operacional(objeto: Any) -> dict[str, Any]:
    from apps.comercial.services.resumo_atendimento_operacional import obter_resumo_atendimento_operacional

    return obter_resumo_atendimento_operacional(objeto)
