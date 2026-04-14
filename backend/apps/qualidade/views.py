from rest_framework import viewsets

from .models import Certificado
from .serializers import CertificadoSerializer


class CertificadoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Certificado.objects.select_related('nf_saida').all()
    serializer_class = CertificadoSerializer
