"""Listagem read-only de usuários para vínculo com colaboradores (Comercial 2.4.2)."""

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ModelSerializer

User = get_user_model()


class UsuarioListSerializer(ModelSerializer):
    """Campos seguros para autocomplete — sem senha, permissões ou grupos."""

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active')
        read_only_fields = fields


class UsuarioViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/usuarios/ — somente leitura."""

    queryset = User.objects.all().order_by('username')
    serializer_class = UsuarioListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('ativo', 'true').lower() in ('1', 'true', 'yes'):
            qs = qs.filter(is_active=True)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search),
            )
        limit_raw = self.request.query_params.get('limit')
        cap = 50
        if limit_raw:
            try:
                cap = max(1, min(int(limit_raw), 100))
            except (TypeError, ValueError):
                pass
        return qs[:cap]
