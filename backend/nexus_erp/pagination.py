"""Paginação padronizada ERP 4.0.5."""

from __future__ import annotations

import math

from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

ALLOWED_PAGE_SIZES = frozenset({20, 50, 100})


class NexusPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None:
            return self.page_size
        try:
            size = int(raw)
        except (TypeError, ValueError):
            return self.page_size
        if size not in ALLOWED_PAGE_SIZES:
            return self.page_size
        return size

    def get_paginated_response(self, data):
        return Response(
            {
                'count': self.page.paginator.count,
                'page': self.page.number,
                'page_size': self.page.paginator.per_page,
                'total_pages': self.page.paginator.num_pages,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data,
            },
        )


def paginate_sequence(request: Request, items: list) -> Response:
    """Pagina lista em memória no envelope padrão Nexus."""
    paginator = NexusPageNumberPagination()
    try:
        page_num = max(1, int(request.query_params.get('page') or 1))
    except (TypeError, ValueError):
        page_num = 1
    page_size = paginator.get_page_size(request)
    count = len(items)
    total_pages = max(1, math.ceil(count / page_size)) if count else 0
    if total_pages and page_num > total_pages:
        page_num = total_pages
    start = (page_num - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    return Response(
        {
            'count': count,
            'page': page_num if count else 1,
            'page_size': page_size,
            'total_pages': total_pages,
            'next': None,
            'previous': None,
            'results': page_items,
        },
    )


def is_autocomplete_request(request: Request) -> bool:
    limit = (request.query_params.get('limit') or '').strip()
    page = (request.query_params.get('page') or '').strip()
    return bool(limit) and not page
