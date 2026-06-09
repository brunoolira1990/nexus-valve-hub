from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination

from .colaborador_acesso import (
    PERFIS_DISPONIVEIS,
    PERFIL_LABELS,
    criar_usuario_para_colaborador,
    definir_perfil_acesso_colaborador,
    desativar_acesso_colaborador,
    editar_acesso_colaborador,
    montar_acesso_colaborador,
    vincular_usuario_colaborador,
)
from .colaborador_senha import redefinir_senha_colaborador, usuario_eh_admin
from .colaborador_sync import sincronizar_vendedor_colaborador, vendedor_id_colaborador
from .models import Colaborador
from .serializers import (
    ColaboradorSerializer,
    CriarUsuarioColaboradorSerializer,
    DefinirPerfilAcessoSerializer,
    EditarAcessoColaboradorSerializer,
    RedefinirSenhaColaboradorSerializer,
    VincularUsuarioColaboradorSerializer,
)

User = get_user_model()

FUNCAO_FILTROS = {
    'vendedor': Q(eh_vendedor=True),
    'comprador': Q(eh_comprador=True),
    'fiscal': Q(eh_responsavel_fiscal=True),
    'financeiro': Q(eh_responsavel_financeiro=True),
    'estoque': Q(eh_responsavel_estoque=True),
    'qualidade': Q(eh_responsavel_qualidade=True),
    'administrador': Q(eh_administrador=True),
}


def _resposta_colaborador(colaborador, request, *, mensagem: str = '', extra: dict | None = None, http_status=200):
    colaborador.refresh_from_db()
    data = ColaboradorSerializer(colaborador, context={'request': request}).data
    if mensagem:
        data['mensagem'] = mensagem
    if extra:
        data.update(extra)
    return Response(data, status=http_status)


class ColaboradorViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = (
        Colaborador.objects.select_related('usuario')
        .prefetch_related('usuario__groups', 'vendedores')
        .all()
    )
    serializer_class = ColaboradorSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        ativo = self.request.query_params.get('ativo')
        if ativo in ('1', 'true', 'True'):
            qs = qs.filter(ativo=True)
        elif ativo in ('0', 'false', 'False'):
            qs = qs.filter(ativo=False)
        funcao = (self.request.query_params.get('funcao') or '').strip().lower()
        if funcao and funcao in FUNCAO_FILTROS:
            qs = qs.filter(FUNCAO_FILTROS[funcao])
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(nome__icontains=search)
                | Q(codigo__icontains=search)
                | Q(email__icontains=search)
                | Q(cargo__icontains=search),
            )
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'nome': 'nome', 'codigo': 'codigo', 'email': 'email'},
            'nome',
        )

    def perform_create(self, serializer):
        colaborador = serializer.save()
        sincronizar_vendedor_colaborador(colaborador)

    def perform_update(self, serializer):
        colaborador = serializer.save()
        sincronizar_vendedor_colaborador(colaborador)

    @action(detail=False, methods=['get'], url_path='vinculado')
    def vinculado(self, request):
        if not request.user.is_authenticated:
            return Response(None)
        c = Colaborador.objects.filter(usuario=request.user, ativo=True).order_by('pk').first()
        if not c:
            return Response(None)
        return Response(ColaboradorSerializer(c, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='perfis-acesso')
    def perfis_acesso(self, request):
        return Response(
            [
                {'value': p, 'label': PERFIL_LABELS.get(p, p.title())}
                for p in PERFIS_DISPONIVEIS
            ],
        )

    @action(detail=True, methods=['post'], url_path='criar-usuario')
    def criar_usuario(self, request, pk=None):
        if not usuario_eh_admin(request.user):
            return Response(
                {'detail': 'Apenas administradores podem criar usuários.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        colaborador = self.get_object()
        ser = CriarUsuarioColaboradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            criar_usuario_para_colaborador(
                colaborador,
                email=ser.validated_data['email'],
                nome=ser.validated_data['nome'],
                perfil=ser.validated_data['perfil'],
                ativo=ser.validated_data.get('ativo', True),
                senha=ser.validated_data['senha'],
                confirmar_senha=ser.validated_data['confirmar_senha'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _resposta_colaborador(
            colaborador,
            request,
            mensagem='Usuário criado e vinculado ao colaborador.',
            http_status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='vincular-usuario')
    def vincular_usuario(self, request, pk=None):
        if not usuario_eh_admin(request.user):
            return Response(
                {'detail': 'Apenas administradores podem vincular usuários.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        colaborador = self.get_object()
        ser = VincularUsuarioColaboradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            vincular_usuario_colaborador(
                colaborador,
                ser.validated_data['usuario'],
                perfil=ser.validated_data.get('perfil'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _resposta_colaborador(colaborador, request, mensagem='Usuário vinculado ao colaborador.')

    @action(detail=True, methods=['post'], url_path='definir-perfil-acesso')
    def definir_perfil_acesso(self, request, pk=None):
        if not usuario_eh_admin(request.user):
            return Response(
                {'detail': 'Apenas administradores podem definir perfil de acesso.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        colaborador = self.get_object()
        ser = DefinirPerfilAcessoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            definir_perfil_acesso_colaborador(colaborador, perfil=ser.validated_data['perfil'])
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _resposta_colaborador(colaborador, request, mensagem='Perfil de acesso definido.')

    @action(detail=True, methods=['patch', 'put'], url_path='acesso')
    def editar_acesso(self, request, pk=None):
        if not usuario_eh_admin(request.user):
            return Response(
                {'detail': 'Apenas administradores podem editar acesso de usuários.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        colaborador = self.get_object()
        ser = EditarAcessoColaboradorSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        try:
            editar_acesso_colaborador(colaborador, actor=request.user, **ser.validated_data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _resposta_colaborador(colaborador, request, mensagem='Acesso atualizado com sucesso.')

    @action(detail=True, methods=['post'], url_path='desativar-acesso')
    def desativar_acesso(self, request, pk=None):
        if not usuario_eh_admin(request.user):
            return Response(
                {'detail': 'Apenas administradores podem desativar acesso.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        colaborador = self.get_object()
        motivo = (request.data.get('motivo') or '').strip()
        try:
            desativar_acesso_colaborador(colaborador, motivo=motivo, actor=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _resposta_colaborador(
            colaborador,
            request,
            mensagem='Acesso desativado. O colaborador permanece cadastrado, mas não poderá acessar o sistema.',
        )

    @action(detail=True, methods=['post'], url_path='redefinir-senha')
    def redefinir_senha(self, request, pk=None):
        if not usuario_eh_admin(request.user):
            return Response(
                {'detail': 'Apenas administradores podem redefinir senha de usuários.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        colaborador = self.get_object()
        ser = RedefinirSenhaColaboradorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            redefinir_senha_colaborador(
                colaborador,
                nova_senha=ser.validated_data['nova_senha'],
                confirmar_senha=ser.validated_data['confirmar_senha'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _resposta_colaborador(colaborador, request, mensagem='Senha redefinida com sucesso.')
