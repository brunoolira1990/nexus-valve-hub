"""
Condição de pagamento canônica da NF-e de saída.

Fonte de verdade do *prazo*: ``NFeSaida.dias_parcelas`` (ArrayField de inteiros),
com fallback para o pedido e, se ainda vazio, parse de ``condicao_pagamento_texto``
via ``parse_payment_condition`` (que já produz o plano canônico).

Esta regra decide somente elegibilidade a cobrança a prazo / Contas a Receber:
- integralmente à vista → ``dias_parcelas == [0]`` → sem duplicatas / sem CR;
- a prazo, misto ou ausente → não tratar como à vista.

Não decide meio de pagamento fiscal (``tPag``). Em NF-e de saída o ``tPag``
continua sendo definido pela rotina pré-existente ``build_pag_bindings``
(heurística baseada na presença de duplicatas na montagem do XML), que esta
tarefa não altera.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.comercial.payment_terms import pagamento_integralmente_a_vista, parse_payment_condition
from apps.fiscal.models import NFeSaida


def resolver_dias_parcelas_nfe(nf: NFeSaida) -> list[int]:
    """Resolve o plano de dias da NF-e (snapshot → pedido → parse do texto)."""
    days = list(nf.dias_parcelas or [])
    if days:
        return days
    pedido = nf.pedido_venda if nf.pedido_venda_id else None
    if pedido and pedido.dias_parcelas:
        return list(pedido.dias_parcelas)
    texto = (nf.condicao_pagamento_texto or '').strip()
    if not texto and pedido:
        texto = (pedido.condicao_pagamento_texto or '').strip()
    if not texto:
        return []
    try:
        return parse_payment_condition(texto)
    except Exception:
        return []


def nfe_venda_integralmente_a_vista(nf: NFeSaida) -> bool:
    """True somente quando o plano canônico da NF-e é ``[0]``."""
    return pagamento_integralmente_a_vista(resolver_dias_parcelas_nfe(nf))


def nfe_deve_gerar_cobranca_a_prazo(nf: NFeSaida) -> bool:
    """
    Indica se a operação deve gerar cobrança/duplicatas e Contas a Receber.

    False apenas para venda integralmente à vista (``[0]``).
    Não define ``tPag`` nem forma/meio de pagamento.
    """
    return not nfe_venda_integralmente_a_vista(nf)


def q_nfe_venda_integralmente_a_vista() -> Q:
    """
    Expressão ORM alinhada a ``nfe_venda_integralmente_a_vista`` para filtros em lote.

    Usa o array persistido na NF-e e, se vazio, o do pedido vinculado.
    Não reparseia texto livre (evita N+1 e inferência textual na listagem).
    """
    dias_nf_vazios = Q(dias_parcelas=[]) | Q(dias_parcelas__isnull=True)
    return Q(dias_parcelas=[0]) | (dias_nf_vazios & Q(pedido_venda__dias_parcelas=[0]))


def filtrar_queryset_deve_gerar_cobranca_a_prazo(qs: QuerySet[NFeSaida]) -> QuerySet[NFeSaida]:
    """Exclui vendas integralmente à vista — equivalente em lote de ``nfe_deve_gerar_cobranca_a_prazo``."""
    return qs.exclude(q_nfe_venda_integralmente_a_vista())
