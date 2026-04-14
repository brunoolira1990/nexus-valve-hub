from decimal import Decimal

from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fiscal.models import NFeSaida


class ApuracaoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mes = int(request.query_params.get('mes', 1))
        ano = int(request.query_params.get('ano', 2024))
        qs = NFeSaida.objects.filter(data__year=ano, data__month=mes)
        receita = qs.aggregate(t=Sum('valor_total'))['t'] or Decimal('0')
        r = float(receita)
        return Response(
            {
                'periodo': f'{mes}/{ano}',
                'receita_bruta': r,
                'irpj': round(r * 0.048, 2),
                'csll': round(r * 0.0288, 2),
                'pis': round(r * 0.0165, 2),
                'cofins': round(r * 0.076, 2),
                'icms': round(r * 0.12, 2),
                'ipi': round(r * 0.05, 2),
                'cbs': round(r * 0.026, 2),
                'ibs': round(r * 0.036, 2),
            }
        )
