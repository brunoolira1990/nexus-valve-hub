import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Cliente, Empresa, Fornecedor, Transportadora
from .serializers import (
    ClienteSerializer,
    EmpresaSerializer,
    FornecedorSerializer,
    TransportadoraSerializer,
)
from django.db.models import Case, Q, When


def _digits_only(s: str) -> str:
    return ''.join(ch for ch in (s or '') if ch.isdigit())


class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().order_by('razao_social')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search),
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().order_by('razao_social')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search)
                | Q(ie__icontains=search),
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs


class FornecedorViewSet(viewsets.ModelViewSet):
    queryset = Fornecedor.objects.all()
    serializer_class = FornecedorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Fornecedor.objects.all()
        search = (self.request.query_params.get('search') or '').strip()
        limit_raw = self.request.query_params.get('limit')
        limit = 20
        if limit_raw:
            try:
                limit = max(1, min(int(limit_raw), 100))
            except (TypeError, ValueError):
                pass

        if not search:
            return qs.order_by('razao_social')

        s = search.strip()
        s_lower = s.lower()
        digits = _digits_only(s)

        q = (
            Q(razao_social__icontains=s)
            | Q(nome_fantasia__icontains=s)
            | Q(cnpj__icontains=s)
            | Q(cidade__icontains=s)
            | Q(uf__icontains=s)
            | Q(ie__icontains=s)
            | Q(telefone__icontains=s)
            | Q(email__icontains=s)
        )
        if len(s) == 2 and s.isalpha():
            q |= Q(uf__iexact=s.upper())

        matched = list(qs.filter(q).distinct()[:250])

        def sort_key(f: Fornecedor):
            cnpj_d = _digits_only(f.cnpj or '')
            rz = (f.razao_social or '').lower()
            nf = (f.nome_fantasia or '').lower()
            if len(digits) == 14 and cnpj_d == digits:
                return (0, rz)
            if rz.startswith(s_lower):
                return (1, rz)
            if nf.startswith(s_lower):
                return (2, rz)
            if s_lower in rz:
                return (3, rz)
            if s_lower in nf:
                return (4, rz)
            if digits and digits in cnpj_d:
                return (5, rz)
            return (6, rz)

        matched.sort(key=sort_key)
        matched = matched[:limit]
        if not matched:
            return qs.none()

        ids = [f.id for f in matched]
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        return qs.filter(pk__in=ids).order_by(preserved)


class TransportadoraViewSet(viewsets.ModelViewSet):
    queryset = Transportadora.objects.all()
    serializer_class = TransportadoraSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().order_by('razao_social')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search)
                | Q(placa_padrao__icontains=search),
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs


def _get_json(url: str, timeout: int = 8) -> dict:
    request = Request(url, headers={"User-Agent": "nexus-valve-hub/1.0"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("Resposta inválida do serviço externo.") from e


def _format_cep_br(digits: str) -> str:
    if len(digits) != 8 or not digits.isdigit():
        return digits
    return f"{digits[:5]}-{digits[5:]}"


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def consulta_cep(request, cep: str):
    cep_digitos = ''.join(ch for ch in str(cep or '') if ch.isdigit())
    if len(cep_digitos) != 8:
        return Response({'detail': 'CEP inválido. Informe 8 dígitos.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _get_json(f'https://viacep.com.br/ws/{cep_digitos}/json/')
    except (HTTPError, URLError, TimeoutError, ValueError):
        return Response(
            {'detail': 'Falha ao consultar o serviço de CEP.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if payload.get('erro'):
        return Response({'detail': 'CEP não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)

    cep_fmt = (payload.get('cep') or '').strip() or _format_cep_br(cep_digitos)

    return Response(
        {
            'logradouro': payload.get('logradouro', '') or '',
            'complemento': payload.get('complemento', '') or '',
            'bairro': payload.get('bairro', '') or '',
            'cidade': payload.get('localidade', '') or '',
            'uf': payload.get('uf', '') or '',
            'cep': cep_fmt,
        }
    )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def consulta_cnpj(request, cnpj: str):
    cnpj_digitos = ''.join(ch for ch in str(cnpj or '') if ch.isdigit())
    if len(cnpj_digitos) != 14:
        return Response({'detail': 'CNPJ inválido. Informe 14 dígitos.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = _get_json(f'https://receitaws.com.br/v1/cnpj/{cnpj_digitos}')
    except (HTTPError, URLError, TimeoutError, ValueError):
        return Response(
            {'detail': 'Falha ao consultar o serviço de CNPJ.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    status_receita = (payload.get('status') or '').lower()
    if status_receita == 'error':
        return Response(
            {'detail': payload.get('message', 'CNPJ não encontrado.')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cep_raw = (payload.get('cep') or '').replace('.', '').replace('-', '').strip()
    cep_fmt = _format_cep_br(cep_raw) if len(cep_raw) == 8 and cep_raw.isdigit() else (payload.get('cep') or '')

    return Response(
        {
            'cnpj': payload.get('cnpj', '') or '',
            'razao_social': payload.get('nome', '') or '',
            'nome_fantasia': payload.get('fantasia', '') or '',
            'logradouro': payload.get('logradouro', '') or '',
            'numero': payload.get('numero', '') or '',
            'complemento': payload.get('complemento', '') or '',
            'bairro': payload.get('bairro', '') or '',
            'cidade': payload.get('municipio', '') or '',
            'uf': payload.get('uf', '') or '',
            'cep': cep_fmt or '',
            'telefone': payload.get('telefone', '') or '',
            'email': payload.get('email', '') or '',
        }
    )
