from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Vendedor
from .serializers import VendedorSerializer

User = get_user_model()


class VendedorViewSet(viewsets.ModelViewSet):
    queryset = Vendedor.objects.select_related('usuario').all()
    serializer_class = VendedorSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('nome')
        if self.request.query_params.get('ativo') in ('1', 'true', 'True'):
            qs = qs.filter(ativo=True)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(nome__icontains=search)
                | Q(codigo__icontains=search)
                | Q(email__icontains=search),
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs

    @action(detail=False, methods=['get'], url_path='vinculado')
    def vinculado(self, request):
        """Vendedor ativo vinculado ao usuário autenticado (default em nova proposta)."""
        if not request.user.is_authenticated:
            return Response(None)
        from apps.cadastros.colaborador_sync import sincronizar_vendedor_colaborador
        from apps.cadastros.models import Colaborador

        colab = (
            Colaborador.objects.filter(usuario=request.user, ativo=True, eh_vendedor=True)
            .order_by('pk')
            .first()
        )
        if colab:
            v = sincronizar_vendedor_colaborador(colab) or Vendedor.objects.filter(
                colaborador=colab, ativo=True,
            ).first()
            if v:
                return Response(VendedorSerializer(v).data)
        v = Vendedor.objects.filter(usuario=request.user, ativo=True).order_by('pk').first()
        if not v:
            return Response(None)
        return Response(VendedorSerializer(v).data)
