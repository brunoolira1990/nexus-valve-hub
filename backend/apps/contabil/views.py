from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Lancamento, PlanoConta
from .serializers import LancamentoSerializer, PlanoContaSerializer


class ContaViewSet(viewsets.ModelViewSet):
    queryset = PlanoConta.objects.select_related('pai').prefetch_related('filhos').all()
    serializer_class = PlanoContaSerializer
    permission_classes = [IsAuthenticated]


class LancamentoViewSet(viewsets.ModelViewSet):
    queryset = Lancamento.objects.select_related('conta').all()
    serializer_class = LancamentoSerializer
    permission_classes = [IsAuthenticated]


class BalanceteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mes = int(request.query_params.get('mes', 1))
        ano = int(request.query_params.get('ano', 2024))
        qs = Lancamento.objects.filter(data__year=ano, data__month=mes).select_related('conta')
        debitos = defaultdict(Decimal)
        creditos = defaultdict(Decimal)
        for l in qs:
            if l.tipo == Lancamento.Tipo.DEBITO:
                debitos[l.conta_id] += l.valor
            else:
                creditos[l.conta_id] += l.valor
        conta_ids = set(debitos) | set(creditos)
        out = []
        for cid in sorted(conta_ids):
            c = PlanoConta.objects.get(pk=cid)
            d = debitos[cid]
            cr = creditos[cid]
            out.append(
                {
                    'conta_id': c.id,
                    'conta_codigo': c.codigo,
                    'conta_nome': c.nome,
                    'debito': float(d),
                    'credito': float(cr),
                    'saldo': float(d - cr),
                }
            )
        return Response(out)
