"""Estoque atual do produto: soma dos saldos das corridas (EstoqueCorrida)."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.fiscal.models import EstoqueCorrida


def _soma_saldos(produto_ref) -> Subquery:
    return (
        EstoqueCorrida.objects.filter(produto_id=produto_ref)
        .values('produto_id')
        .annotate(total=Sum('saldo'))
        .values('total')
    )


def subquery_estoque_atual() -> Coalesce:
    """Subquery em vez de Sum('estoques_corrida__saldo'): o join do annotate somaria linhas
    repetidas pelo filtro da listagem e deixaria o saldo NULL para produto sem corrida."""
    return Coalesce(
        _soma_saldos(OuterRef('pk')),
        Value(Decimal('0')),
        output_field=DecimalField(max_digits=20, decimal_places=3),
    )


def annotate_estoque_atual(queryset):
    return queryset.annotate(estoque_atual=subquery_estoque_atual())


def estoque_atual_produto(produto_id: int) -> Decimal:
    total = EstoqueCorrida.objects.filter(produto_id=produto_id).aggregate(total=Sum('saldo'))['total']
    return Decimal(str(total or 0))
