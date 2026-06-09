"""Mixins de listagem — busca, ordenação e compatibilidade autocomplete (limit)."""

from __future__ import annotations

from rest_framework.response import Response

from nexus_erp.pagination import NexusPageNumberPagination


class AutocompleteOrPaginationMixin:
    """Com `limit` sem `page` retorna array simples (autocomplete). Caso contrário, pagina."""

    pagination_class = NexusPageNumberPagination

    def list(self, request, *args, **kwargs):
        limit = (request.query_params.get('limit') or '').strip()
        page = (request.query_params.get('page') or '').strip()
        if limit and not page:
            qs = self.filter_queryset(self.get_queryset())
            try:
                n = max(1, min(int(limit), 100))
            except (TypeError, ValueError):
                n = 20
            qs = qs[:n]
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)


def aplicar_ordering(qs, ordering_param: str | None, allowed: dict[str, str], default: str):
    key = (ordering_param or '').strip()
    if not key:
        return qs.order_by(default)
    desc = key.startswith('-')
    field_key = key.lstrip('-')
    db_field = allowed.get(field_key)
    if not db_field:
        return qs.order_by(default)
    if desc:
        db_field = f'-{db_field}'
    return qs.order_by(db_field)
