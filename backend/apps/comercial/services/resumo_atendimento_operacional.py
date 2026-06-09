"""ERP 4.0.11 — resumo read-only de atendimento operacional (AlocacaoAtendimento).

Visibilidade informativa em PV, faturamento e NF-e Saída. Não altera banco,
estoque, financeiro nem emissão fiscal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db.models import Q, QuerySet

from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)


class BadgeOperacional(TypedDict):
    label: str
    status: str
    variant: str


def _dec(v: Decimal | str | float | int | None) -> Decimal:
    if v is None:
        return Decimal('0')
    return Decimal(str(v))


def _query_alocacoes(obj: Any) -> QuerySet:
    from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
    from apps.fiscal.models import AlocacaoAtendimento, ItemNFeSaida, NFeSaida

    if isinstance(obj, PedidoVenda):
        return AlocacaoAtendimento.objects.filter(pedido_venda_item__pedido_id=obj.pk)
    if isinstance(obj, ItemPedidoVenda):
        return AlocacaoAtendimento.objects.filter(pedido_venda_item_id=obj.pk)
    if isinstance(obj, FaturamentoPedidoVenda):
        q = Q(faturamento_item__faturamento_id=obj.pk)
        if obj.pedido_id:
            q |= Q(pedido_venda_item__pedido_id=obj.pedido_id)
        return AlocacaoAtendimento.objects.filter(q)
    if isinstance(obj, NFeSaida):
        q = Q(item_nf_saida__nf_id=obj.pk)
        if obj.faturamento_pedido_venda_id:
            q |= Q(faturamento_item__faturamento_id=obj.faturamento_pedido_venda_id)
        if obj.pedido_venda_id:
            q |= Q(pedido_venda_item__pedido_id=obj.pedido_venda_id)
        return AlocacaoAtendimento.objects.filter(q)
    if isinstance(obj, ItemNFeSaida):
        q = Q(item_nf_saida_id=obj.pk)
        nf = obj.nf
        if nf.faturamento_pedido_venda_id:
            q |= Q(faturamento_item__faturamento_id=nf.faturamento_pedido_venda_id)
        if nf.pedido_venda_id:
            q |= Q(pedido_venda_item__pedido_id=nf.pedido_venda_id)
        return AlocacaoAtendimento.objects.filter(q)
    # ItemFaturamentoPedidoVenda
    faturamento_item_id = getattr(obj, 'pk', None)
    faturamento_id = getattr(getattr(obj, 'faturamento', None), 'pk', None)
    if faturamento_item_id and hasattr(obj, 'faturamento_id'):
        q = Q(faturamento_item_id=faturamento_item_id)
        if faturamento_id:
            q |= Q(faturamento_item__faturamento_id=faturamento_id)
        return AlocacaoAtendimento.objects.filter(q)
    return AlocacaoAtendimento.objects.none()


def _variant_badge(status: str) -> str:
    mapping = {
        'entrada_pendente': 'warning',
        'entrada_conciliada': 'success',
        'retirada_fornecedor': 'info',
        'retirada_fornecedor_transportadora': 'info',
        'entrega_direta': 'info',
        'atendimento_misto': 'warning',
        'nao_definido': 'neutral',
        'divergente': 'danger',
        'recebida': 'info',
        'conciliada': 'success',
    }
    return mapping.get(status, 'neutral')


def _badge(label: str, status: str) -> BadgeOperacional:
    return {'label': label, 'status': status, 'variant': _variant_badge(status)}


_LABEL_TIPO: dict[str, str] = {
    TipoAtendimentoItem.NAO_DEFINIDO: 'Atendimento não definido',
    TipoAtendimentoItem.RETIRADA_FORNECEDOR: 'Retirada no fornecedor',
    TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA: 'Retirada fornecedor → transportadora',
    TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE: 'Entrega direta',
    TipoAtendimentoItem.ENTRADA_CONCILIADA: 'Entrada conciliada',
    TipoAtendimentoItem.MISTO: 'Atendimento misto',
    TipoAtendimentoItem.COMPRA_VINCULADA: 'Compra vinculada',
    TipoAtendimentoItem.ESTOQUE_PROPRIO: 'Estoque próprio',
}

_LABEL_STATUS_ENTRADA: dict[str, str] = {
    StatusEntradaFiscal.PENDENTE: 'Entrada pendente',
    StatusEntradaFiscal.CONCILIADA: 'Entrada conciliada',
    StatusEntradaFiscal.RECEBIDA: 'Recebida',
    StatusEntradaFiscal.DIVERGENTE: 'Divergente',
    StatusEntradaFiscal.NAO_APLICAVEL: 'Não aplicável',
}

_LABEL_ORIGEM: dict[str, str] = {
    OrigemFisica.FORNECEDOR: 'Fornecedor',
    OrigemFisica.ESTOQUE_PROPRIO: 'Estoque próprio',
    OrigemFisica.TRANSPORTADORA: 'Transportadora',
    OrigemFisica.CLIENTE: 'Cliente',
    OrigemFisica.TERCEIRO: 'Terceiro',
    OrigemFisica.NAO_DEFINIDA: 'Indefinida',
}

_LABEL_DESTINO: dict[str, str] = {
    DestinoFisico.CLIENTE: 'Cliente',
    DestinoFisico.TRANSPORTADORA: 'Transportadora',
    DestinoFisico.ESTOQUE_PROPRIO: 'Estoque próprio',
    DestinoFisico.TERCEIRO: 'Terceiro',
    DestinoFisico.NAO_DEFINIDO: 'Indefinido',
}


def _tipo_atendimento_agregado(*, atendimento_misto: bool, tipo_principal: str) -> str:
    if atendimento_misto:
        return 'atendimento_misto'
    mapping = {
        TipoAtendimentoItem.RETIRADA_FORNECEDOR: 'retirada_fornecedor',
        TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA: 'retirada_fornecedor',
        TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE: 'entrega_direta',
        TipoAtendimentoItem.ENTRADA_CONCILIADA: 'entrada_conciliada',
    }
    return mapping.get(tipo_principal, 'nao_definido')


def _sem_alocacao() -> dict[str, Any]:
    return {
        'tem_alocacao': False,
        'tipo_atendimento': 'nao_definido',
        'tipo_atendimento_label': 'Atendimento não definido',
        'status_entrada_fiscal': 'indefinido',
        'status_entrada_fiscal_label': 'Indefinido',
        'origem_fisica': 'indefinida',
        'origem_fisica_label': 'Indefinida',
        'destino_fisico': 'indefinido',
        'destino_fisico_label': 'Indefinido',
        'tem_compra_vinculada': False,
        'tem_nfe_entrada_vinculada': False,
        'tem_cte_vinculado': False,
        'itens_total': 0,
        'itens_com_entrada_pendente': 0,
        'itens_com_entrada_conciliada': 0,
        'itens_entrega_direta': 0,
        'itens_retirada_fornecedor': 0,
        'alertas': [],
        'badges': [_badge('Atendimento não definido', 'nao_definido')],
        'mensagem': (
            'Atendimento operacional ainda não definido. Use esta seção para informar '
            'retirada no fornecedor, entrega direta, entrada pendente ou entrada conciliada.'
        ),
    }


def _tipo_para_badge(tipo: str) -> BadgeOperacional | None:
    mapping: dict[str, tuple[str, str]] = {
        TipoAtendimentoItem.RETIRADA_FORNECEDOR: ('Retirada fornecedor', 'retirada_fornecedor'),
        TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA: (
            'Retirada fornecedor → transportadora',
            'retirada_fornecedor_transportadora',
        ),
        TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE: ('Entrega direta', 'entrega_direta'),
        TipoAtendimentoItem.ENTRADA_CONCILIADA: ('Entrada conciliada', 'entrada_conciliada'),
        TipoAtendimentoItem.MISTO: ('Atendimento misto', 'atendimento_misto'),
    }
    if tipo in mapping:
        label, status = mapping[tipo]
        return _badge(label, status)
    return None


def _status_entrada_para_badge(status: str) -> BadgeOperacional | None:
    mapping: dict[str, tuple[str, str]] = {
        StatusEntradaFiscal.PENDENTE: ('Entrada pendente', 'entrada_pendente'),
        StatusEntradaFiscal.CONCILIADA: ('Entrada conciliada', 'entrada_conciliada'),
        StatusEntradaFiscal.RECEBIDA: ('Recebida', 'recebida'),
        StatusEntradaFiscal.DIVERGENTE: ('Divergente', 'divergente'),
    }
    if status in mapping:
        label, st = mapping[status]
        return _badge(label, st)
    return None


def _prioridade_tipo(tipo: str) -> int:
    order = {
        TipoAtendimentoItem.MISTO: 0,
        TipoAtendimentoItem.RETIRADA_FORNECEDOR: 1,
        TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA: 2,
        TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE: 3,
        TipoAtendimentoItem.ENTRADA_CONCILIADA: 4,
        TipoAtendimentoItem.COMPRA_VINCULADA: 5,
        TipoAtendimentoItem.ESTOQUE_PROPRIO: 6,
        TipoAtendimentoItem.NAO_DEFINIDO: 99,
    }
    return order.get(tipo, 50)


def _prioridade_status_entrada(status: str) -> int:
    order = {
        StatusEntradaFiscal.DIVERGENTE: 0,
        StatusEntradaFiscal.PENDENTE: 1,
        StatusEntradaFiscal.RECEBIDA: 2,
        StatusEntradaFiscal.CONCILIADA: 3,
        StatusEntradaFiscal.NAO_APLICAVEL: 99,
    }
    return order.get(status, 50)


def _montar_mensagem(
    *,
    possui_divergencia: bool,
    possui_entrada_pendente: bool,
    possui_entrada_conciliada: bool,
    possui_retirada_fornecedor: bool,
    possui_entrega_direta: bool,
    atendimento_misto: bool,
    contexto: str = 'documento',
) -> str:
    if possui_divergencia:
        return 'Há divergência na conciliação de entrada fiscal deste atendimento.'
    if atendimento_misto:
        return 'Atendimento misto: combina estoque, fornecedor e/ou entradas fiscais em diferentes estágios.'
    partes: list[str] = []
    if possui_retirada_fornecedor:
        partes.append('retirada no fornecedor')
    if possui_entrega_direta:
        partes.append('entrega direta fornecedor → cliente')
    if possui_entrada_pendente:
        partes.append('entrada fiscal pendente')
    if possui_entrada_conciliada:
        partes.append('entrada fiscal conciliada')
    if not partes:
        return 'Atendimento operacional registrado.'
    if contexto == 'nfe_saida' and possui_retirada_fornecedor and possui_entrada_pendente:
        return (
            'NF-e de saída vinculada a atendimento com retirada no fornecedor. '
            'A entrada fiscal do fornecedor será conciliada posteriormente.'
        )
    if contexto == 'nfe_saida' and possui_entrada_conciliada and not possui_entrada_pendente:
        return 'Entrada fiscal do fornecedor já conciliada para este atendimento.'
    return f'Atendimento com {" e ".join(partes)}.'


def _coletar_alocacoes_prefetch_pedido(pedido) -> list:
    """Usa prefetch de itens__alocacoes_atendimento quando disponível (evita N+1 na listagem)."""
    cache = getattr(pedido, '_prefetched_objects_cache', None) or {}
    if 'itens' not in cache:
        return []
    out: list = []
    for item in pedido.itens.all():
        item_cache = getattr(item, '_prefetched_objects_cache', None) or {}
        if 'alocacoes_atendimento' in item_cache:
            out.extend(item.alocacoes_atendimento.all())
    return out


def _alocacoes_para_objeto(objeto: Any) -> list:
    from apps.comercial.models import PedidoVenda

    if isinstance(objeto, PedidoVenda):
        pref = _coletar_alocacoes_prefetch_pedido(objeto)
        if pref:
            return pref
    qs = _query_alocacoes(objeto)
    return list(qs.distinct())


def _vinculos_from_alocacoes(alocacoes: list) -> tuple[bool, bool, bool]:
    tem_compra = any(getattr(a, 'pedido_compra_item_id', None) for a in alocacoes)
    tem_nfe_entrada = any(
        getattr(a, 'nf_entrada_item_id', None) or getattr(a, 'nf_entrada_historica_item_id', None)
        for a in alocacoes
    )
    tem_cte = any(
        getattr(a, 'cte_historico_importado_id', None)
        or (
            getattr(a, 'nf_entrada_item', None)
            and getattr(getattr(a.nf_entrada_item, 'nf', None), 'cte_id', None)
        )
        for a in alocacoes
    )
    return tem_compra, tem_nfe_entrada, tem_cte


def _contagens_itens(alocacoes: list) -> dict[str, int]:
    itens_pv = {a.pedido_venda_item_id for a in alocacoes if a.pedido_venda_item_id}
    itens_fat = {a.faturamento_item_id for a in alocacoes if a.faturamento_item_id}
    itens_nf = {a.item_nf_saida_id for a in alocacoes if a.item_nf_saida_id}
    total = len(itens_pv or itens_fat or itens_nf) or len(alocacoes)
    pendente = sum(1 for a in alocacoes if a.status_entrada_fiscal == StatusEntradaFiscal.PENDENTE)
    conciliada = sum(1 for a in alocacoes if a.status_entrada_fiscal == StatusEntradaFiscal.CONCILIADA)
    entrega = sum(
        1 for a in alocacoes if a.tipo_atendimento == TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE
    )
    retirada = sum(
        1
        for a in alocacoes
        if a.tipo_atendimento
        in (TipoAtendimentoItem.RETIRADA_FORNECEDOR, TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA)
    )
    return {
        'itens_total': total,
        'itens_com_entrada_pendente': pendente,
        'itens_com_entrada_conciliada': conciliada,
        'itens_entrega_direta': entrega,
        'itens_retirada_fornecedor': retirada,
    }


def _montar_alertas(
    *,
    contexto: str,
    possui_entrada_pendente: bool,
    tem_compra: bool,
    tem_nfe_entrada: bool,
    tem_cte: bool,
    atendimento_misto: bool,
) -> list[str]:
    alertas: list[str] = []
    if contexto == 'nfe_saida' and possui_entrada_pendente:
        alertas.append(
            'Entrada fiscal ainda não conciliada. Operação permitida; sem bloqueio automático.',
        )
    if not tem_compra:
        alertas.append('Não há pedido de compra vinculado a este atendimento.')
    if atendimento_misto:
        alertas.append('Este documento possui itens com tipos de atendimento diferentes.')
    if tem_cte:
        alertas.append('Existe CT-e vinculado à operação (referência informativa).')
    elif tem_nfe_entrada or possui_entrada_pendente:
        alertas.append('Nenhum CT-e conferido vinculado.')
    return alertas


def _montar_resumo_from_alocacoes(alocacoes: list, *, contexto: str = 'documento') -> dict[str, Any]:
    if not alocacoes:
        return _sem_alocacao()

    tipos = {a.tipo_atendimento for a in alocacoes if a.tipo_atendimento != TipoAtendimentoItem.NAO_DEFINIDO}
    status_entradas = {a.status_entrada_fiscal for a in alocacoes}

    possui_divergencia = StatusEntradaFiscal.DIVERGENTE in status_entradas
    possui_entrada_pendente = StatusEntradaFiscal.PENDENTE in status_entradas
    possui_entrada_conciliada = StatusEntradaFiscal.CONCILIADA in status_entradas
    possui_recebida = StatusEntradaFiscal.RECEBIDA in status_entradas
    possui_retirada_fornecedor = any(
        a.tipo_atendimento
        in (
            TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA,
        )
        for a in alocacoes
    )
    possui_entrega_direta = any(
        a.tipo_atendimento == TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE for a in alocacoes
    )
    atendimento_misto = (
        TipoAtendimentoItem.MISTO in tipos
        or len(tipos) > 1
        or (possui_retirada_fornecedor and possui_entrega_direta)
        or (possui_entrada_conciliada and possui_entrada_pendente)
    )

    qtd_pendente = sum(_dec(a.quantidade_pendente) for a in alocacoes)
    qtd_conciliada = sum(
        _dec(a.quantidade_atendida)
        for a in alocacoes
        if a.status_entrada_fiscal == StatusEntradaFiscal.CONCILIADA
    )

    tipo_principal = min(
        (a.tipo_atendimento for a in alocacoes),
        key=_prioridade_tipo,
        default=TipoAtendimentoItem.NAO_DEFINIDO,
    )
    status_entrada_principal = min(
        (a.status_entrada_fiscal for a in alocacoes),
        key=_prioridade_status_entrada,
        default=StatusEntradaFiscal.NAO_APLICAVEL,
    )
    origem_principal = min(
        (a.origem_fisica for a in alocacoes),
        key=lambda x: 0 if x != OrigemFisica.NAO_DEFINIDA else 99,
        default=OrigemFisica.NAO_DEFINIDA,
    )
    destino_principal = min(
        (a.destino_fisico for a in alocacoes),
        key=lambda x: 0 if x != DestinoFisico.NAO_DEFINIDO else 99,
        default=DestinoFisico.NAO_DEFINIDO,
    )

    badges: list[BadgeOperacional] = []
    seen: set[str] = set()

    def _add(b: BadgeOperacional | None) -> None:
        if b and b['status'] not in seen:
            seen.add(b['status'])
            badges.append(b)

    if atendimento_misto:
        _add(_badge('Atendimento misto', 'atendimento_misto'))
    for st in (
        StatusEntradaFiscal.DIVERGENTE,
        StatusEntradaFiscal.PENDENTE,
        StatusEntradaFiscal.RECEBIDA,
        StatusEntradaFiscal.CONCILIADA,
    ):
        if st in status_entradas:
            _add(_status_entrada_para_badge(st))
    for tipo in sorted(tipos, key=_prioridade_tipo):
        _add(_tipo_para_badge(tipo))

    if not badges:
        _add(_badge('Atendimento não definido', 'nao_definido'))

    mensagem = _montar_mensagem(
        possui_divergencia=possui_divergencia,
        possui_entrada_pendente=possui_entrada_pendente,
        possui_entrada_conciliada=possui_entrada_conciliada or possui_recebida,
        possui_retirada_fornecedor=possui_retirada_fornecedor,
        possui_entrega_direta=possui_entrega_direta,
        atendimento_misto=atendimento_misto,
        contexto=contexto,
    )

    tipo_agregado = _tipo_atendimento_agregado(
        atendimento_misto=atendimento_misto,
        tipo_principal=tipo_principal,
    )
    status_entrada_api = (
        'entrada_pendente'
        if possui_entrada_pendente
        else 'entrada_conciliada'
        if possui_entrada_conciliada
        else 'nao_aplicavel'
        if status_entrada_principal == StatusEntradaFiscal.NAO_APLICAVEL
        else 'indefinido'
    )
    tem_compra, tem_nfe_entrada, tem_cte = _vinculos_from_alocacoes(alocacoes)
    contagens = _contagens_itens(alocacoes)
    alertas = _montar_alertas(
        contexto=contexto,
        possui_entrada_pendente=possui_entrada_pendente,
        tem_compra=tem_compra,
        tem_nfe_entrada=tem_nfe_entrada,
        tem_cte=tem_cte,
        atendimento_misto=atendimento_misto,
    )

    badges_extras: list[BadgeOperacional] = []
    if tem_compra:
        badges_extras.append(_badge('Compra vinculada', 'compra_vinculada'))
    else:
        badges_extras.append(_badge('Sem compra vinculada', 'sem_compra_vinculada'))
    if tem_cte:
        badges_extras.append(_badge('CT-e conferido', 'cte_conferido'))
    badges_extras.append(_badge('Sem bloqueio operacional', 'sem_bloqueio_operacional'))
    for b in badges_extras:
        if b['status'] not in seen:
            badges.append(b)

    return {
        'tem_alocacao': True,
        'tipo_atendimento': tipo_agregado,
        'tipo_atendimento_label': _LABEL_TIPO.get(tipo_principal, 'Atendimento operacional'),
        'status_entrada_fiscal': status_entrada_api,
        'status_entrada_fiscal_label': _LABEL_STATUS_ENTRADA.get(
            status_entrada_principal,
            'Indefinido',
        ),
        'origem_fisica': origem_principal.lower() if origem_principal else 'indefinida',
        'origem_fisica_label': _LABEL_ORIGEM.get(origem_principal, 'Indefinida'),
        'destino_fisico': destino_principal.lower() if destino_principal else 'indefinido',
        'destino_fisico_label': _LABEL_DESTINO.get(destino_principal, 'Indefinido'),
        'tem_compra_vinculada': tem_compra,
        'tem_nfe_entrada_vinculada': tem_nfe_entrada,
        'tem_cte_vinculado': tem_cte,
        **contagens,
        'alertas': alertas,
        'tipo_principal': tipo_principal,
        'status_entrada_principal': status_entrada_principal,
        'origem_fisica_principal': origem_principal,
        'destino_fisico_principal': destino_principal,
        'quantidade_itens': len(alocacoes),
        'quantidade_pendente': str(qtd_pendente),
        'quantidade_conciliada': str(qtd_conciliada),
        'possui_entrada_pendente': possui_entrada_pendente,
        'possui_entrada_conciliada': possui_entrada_conciliada,
        'possui_divergencia': possui_divergencia,
        'possui_retirada_fornecedor': possui_retirada_fornecedor,
        'possui_entrega_direta': possui_entrega_direta,
        'atendimento_misto': atendimento_misto,
        'badges': badges[:6],
        'mensagem': mensagem,
    }


def _montar_resumo_from_queryset(qs: QuerySet, *, contexto: str = 'documento') -> dict[str, Any]:
    return _montar_resumo_from_alocacoes(list(qs.distinct()), contexto=contexto)


def obter_resumo_atendimento_operacional(
    objeto: Any,
    *,
    enxuto: bool = False,
    contexto: str = 'documento',
) -> dict[str, Any]:
    """Monta resumo read-only a partir de AlocacaoAtendimento."""
    alocacoes = _alocacoes_para_objeto(objeto)
    resumo = _montar_resumo_from_alocacoes(alocacoes, contexto=contexto)

    if enxuto:
        return {
            'tem_alocacao': resumo.get('tem_alocacao', False),
            'badges': (resumo.get('badges') or [])[:3],
            'mensagem': resumo.get('mensagem', ''),
            'tipo_atendimento': resumo.get('tipo_atendimento'),
            'status_entrada_fiscal': resumo.get('status_entrada_fiscal'),
        }
    return resumo


def obter_resumo_atendimento_pv(pedido_venda) -> dict[str, Any]:
    return obter_resumo_atendimento_operacional(pedido_venda, contexto='pedido_venda')


def obter_resumo_atendimento_faturamento(faturamento) -> dict[str, Any]:
    return obter_resumo_atendimento_operacional(faturamento, contexto='faturamento')


def obter_resumo_atendimento_nfe_saida(nfe_saida) -> dict[str, Any]:
    return obter_resumo_atendimento_operacional(nfe_saida, contexto='nfe_saida')


def resumo_enxuto_listagem(objeto: Any, *, contexto: str = 'documento') -> dict[str, Any]:
    """Resumo compacto para listagens (máx. 3 badges). Sempre retorna estrutura mínima."""
    return obter_resumo_atendimento_operacional(objeto, enxuto=True, contexto=contexto)


def resumo_listagem_pedido_venda(pedido_venda) -> dict[str, Any]:
    """Listagem PV: exibe «não definido» quando sem alocação."""
    return resumo_enxuto_listagem(pedido_venda, contexto='pedido_venda')
