"""Ordem de exibição de itens em documentos comerciais e fiscais — ordem de inclusão."""

from __future__ import annotations

from typing import Iterable, TypeVar

T = TypeVar('T')


def _chave_inclusao(obj) -> int:
    return int(getattr(obj, 'pk', None) or getattr(obj, 'id', 0) or 0)


def ordenar_itens_por_inclusao(queryset):
    """QuerySet de linhas com pk/id — ordem de inclusão (id ASC)."""
    return queryset.order_by('id')


def listar_itens_por_inclusao(queryset_ou_iteravel: Iterable[T]) -> list[T]:
    """Lista itens na ordem de inclusão (id ASC)."""
    if hasattr(queryset_ou_iteravel, 'order_by'):
        return list(ordenar_itens_por_inclusao(queryset_ou_iteravel))  # type: ignore[arg-type]
    return sorted(queryset_ou_iteravel, key=_chave_inclusao)
