from django.db.models import Q
from rest_framework import permissions, viewsets

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

from .models import Lead, Oportunidade
from .serializers import LeadSerializer, OportunidadeSerializer


class LeadViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Lead.objects.select_related('responsavel', 'cliente').all()
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination
    search_fields = ('nome', 'cnpj', 'nome_contato', 'email', 'telefone')
    ordering_fields = ('nome', 'status', 'origem', 'criado_em', 'atualizado_em')
    ordering_map = {
        'nome': 'nome',
        '-nome': '-nome',
        'status': 'status',
        '-status': '-status',
        'criado_em': 'criado_em',
        '-criado_em': '-criado_em',
        'atualizado_em': 'atualizado_em',
        '-atualizado_em': '-atualizado_em',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        status = params.get('status')
        origem = params.get('origem')
        responsavel_id = params.get('responsavel_id')
        if status:
            queryset = queryset.filter(status=status)
        if origem:
            queryset = queryset.filter(origem=origem)
        if responsavel_id:
            queryset = queryset.filter(responsavel_id=responsavel_id)
        search = (params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(nome_contato__icontains=search)
                | Q(email__icontains=search)
                | Q(telefone__icontains=search)
            )
        return aplicar_ordering(
            queryset,
            params.get('ordering'),
            self.ordering_map,
            '-atualizado_em',
        )


class OportunidadeViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Oportunidade.objects.select_related('lead', 'cliente', 'responsavel').all()
    serializer_class = OportunidadeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination
    search_fields = ('titulo', 'lead__nome', 'cliente__razao_social', 'cliente__nome_fantasia')
    ordering_fields = (
        'titulo',
        'status',
        'etapa',
        'valor_estimado',
        'previsao_fechamento',
        'proxima_acao',
        'criado_em',
        'atualizado_em',
    )
    ordering_map = {
        'titulo': 'titulo',
        '-titulo': '-titulo',
        'status': 'status',
        '-status': '-status',
        'etapa': 'etapa',
        '-etapa': '-etapa',
        'valor_estimado': 'valor_estimado',
        '-valor_estimado': '-valor_estimado',
        'previsao_fechamento': 'previsao_fechamento',
        '-previsao_fechamento': '-previsao_fechamento',
        'atualizado_em': 'atualizado_em',
        '-atualizado_em': '-atualizado_em',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        status = params.get('status')
        etapa = params.get('etapa')
        responsavel_id = params.get('responsavel_id')
        cliente_id = params.get('cliente_id')
        if status:
            queryset = queryset.filter(status=status)
        if etapa:
            queryset = queryset.filter(etapa=etapa)
        if responsavel_id:
            queryset = queryset.filter(responsavel_id=responsavel_id)
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)
        search = (params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search)
                | Q(lead__nome__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente__nome_fantasia__icontains=search)
            )
        return aplicar_ordering(
            queryset,
            params.get('ordering'),
            self.ordering_map,
            '-atualizado_em',
        )
