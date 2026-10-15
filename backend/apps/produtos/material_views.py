"""ViewSet para Material."""

from __future__ import annotations

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from nexus_erp.pagination import NexusPageNumberPagination

from apps.produtos.material_models import Material
from apps.produtos.material_serializers import MaterialSerializer


class MaterialViewSet(viewsets.ModelViewSet):
    """CRUD de materiais de engenharia.

    Endpoints automáticos via DefaultRouter:
        GET    /api/materiais/          — lista paginada
        POST   /api/materiais/          — cria
        GET    /api/materiais/{id}/     — detalhe
        PATCH  /api/materiais/{id}/     — atualiza parcialmente
        PUT    /api/materiais/{id}/     — atualiza completamente
        DELETE /api/materiais/{id}/     — remove

    Query params suportados:
        ?search=<termo>      — busca em nome, codigo e aliases
        ?categoria=ACO_INOX  — filtra por categoria
        ?ativo=true|false    — filtra por status
        ?ordering=nome       — ordenação (nome, ordem, categoria, codigo)
    """

    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = Material.objects.all()

        # Filtro por categoria
        categoria = self.request.query_params.get('categoria')
        if categoria:
            qs = qs.filter(categoria=categoria)

        # Filtro por ativo
        ativo_param = self.request.query_params.get('ativo')
        if ativo_param is not None:
            ativo_param = ativo_param.lower()
            if ativo_param in ('true', '1'):
                qs = qs.filter(ativo=True)
            elif ativo_param in ('false', '0'):
                qs = qs.filter(ativo=False)

        # Busca textual: nome, codigo, aliases (icontains no JSON cast)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(nome__icontains=search)
                | Q(nome_curto__icontains=search)
                | Q(codigo__icontains=search)
                | Q(aliases__icontains=search)
            )

        # Ordenação
        ordering = self.request.query_params.get('ordering', '')
        allowed = {'nome', '-nome', 'ordem', '-ordem', 'categoria', '-categoria',
                   'codigo', '-codigo'}
        if ordering in allowed:
            qs = qs.order_by(ordering)

        return qs
