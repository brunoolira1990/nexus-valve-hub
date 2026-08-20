from django.db.models import Q
from rest_framework import permissions, viewsets

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

from .models import Atividade, HistoricoLead, Lead, Oportunidade
from .serializers import AtividadeSerializer, HistoricoLeadSerializer, LeadSerializer, OportunidadeSerializer


def registrar_historico_lead(*, lead, evento, titulo, descricao='', atividade=None, realizado_por=None, dados=None):
    if not lead:
        return
    HistoricoLead.objects.create(
        lead=lead,
        evento=evento,
        titulo=titulo,
        descricao=descricao,
        atividade=atividade,
        realizado_por=realizado_por,
        dados=dados or {},
    )


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

    def perform_create(self, serializer):
        lead = serializer.save()
        registrar_historico_lead(
            lead=lead,
            evento=HistoricoLead.Evento.CRIADO,
            titulo='Lead criado',
            descricao='Lead incluído no CRM.',
            realizado_por=getattr(self.request.user, 'colaborador', None),
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        status_anterior = instance.status
        responsavel_anterior = instance.responsavel_id
        lead = serializer.save()
        realizado_por = getattr(self.request.user, 'colaborador', None)
        if status_anterior != lead.status:
            registrar_historico_lead(
                lead=lead,
                evento=HistoricoLead.Evento.STATUS_ALTERADO,
                titulo='Status do lead alterado',
                descricao=f'{status_anterior} → {lead.status}',
                realizado_por=realizado_por,
                dados={'de': status_anterior, 'para': lead.status},
            )
        if responsavel_anterior != lead.responsavel_id:
            registrar_historico_lead(
                lead=lead,
                evento=HistoricoLead.Evento.RESPONSAVEL_ALTERADO,
                titulo='Responsável do lead alterado',
                realizado_por=realizado_por,
                dados={'de': responsavel_anterior, 'para': lead.responsavel_id},
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


class AtividadeViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Atividade.objects.select_related('lead', 'oportunidade', 'responsavel').all()
    serializer_class = AtividadeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination
    search_fields = ('titulo', 'descricao', 'lead__nome', 'oportunidade__titulo')
    ordering_fields = ('titulo', 'tipo', 'status', 'agendada_para', 'criado_em', 'atualizado_em')
    ordering_map = {
        'titulo': 'titulo',
        '-titulo': '-titulo',
        'tipo': 'tipo',
        '-tipo': '-tipo',
        'status': 'status',
        '-status': '-status',
        'agendada_para': 'agendada_para',
        '-agendada_para': '-agendada_para',
        'criado_em': 'criado_em',
        '-criado_em': '-criado_em',
        'atualizado_em': 'atualizado_em',
        '-atualizado_em': '-atualizado_em',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for field in ('lead_id', 'oportunidade_id', 'responsavel_id', 'status', 'tipo'):
            value = params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        search = (params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(lead__nome__icontains=search)
                | Q(oportunidade__titulo__icontains=search)
            )
        return aplicar_ordering(queryset, params.get('ordering'), self.ordering_map, 'agendada_para')

    def perform_create(self, serializer):
        atividade = serializer.save()
        lead = atividade.lead or getattr(atividade.oportunidade, 'lead', None)
        registrar_historico_lead(
            lead=lead,
            evento=HistoricoLead.Evento.ATIVIDADE_CRIADA,
            titulo='Atividade criada',
            descricao=atividade.titulo,
            atividade=atividade,
            realizado_por=getattr(self.request.user, 'colaborador', None),
            dados={'tipo': atividade.tipo, 'status': atividade.status},
        )

    def perform_update(self, serializer):
        atividade_anterior = self.get_object()
        atividade = serializer.save()
        lead = atividade.lead or getattr(atividade.oportunidade, 'lead', None)
        registrar_historico_lead(
            lead=lead,
            evento=HistoricoLead.Evento.ATIVIDADE_ATUALIZADA,
            titulo='Atividade atualizada',
            descricao=atividade.titulo,
            atividade=atividade,
            realizado_por=getattr(self.request.user, 'colaborador', None),
            dados={
                'status_anterior': atividade_anterior.status,
                'status_atual': atividade.status,
            },
        )


class HistoricoLeadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoricoLead.objects.select_related('lead', 'atividade', 'realizado_por').all()
    serializer_class = HistoricoLeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NexusPageNumberPagination
    search_fields = ('titulo', 'descricao', 'lead__nome')
    ordering_fields = ('criado_em', 'evento', 'titulo')
    ordering_map = {
        'criado_em': 'criado_em',
        '-criado_em': '-criado_em',
        'evento': 'evento',
        '-evento': '-evento',
        'titulo': 'titulo',
        '-titulo': '-titulo',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        lead_id = params.get('lead_id')
        evento = params.get('evento')
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)
        if evento:
            queryset = queryset.filter(evento=evento)
        search = (params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(lead__nome__icontains=search)
            )
        return aplicar_ordering(queryset, params.get('ordering'), self.ordering_map, '-criado_em')
