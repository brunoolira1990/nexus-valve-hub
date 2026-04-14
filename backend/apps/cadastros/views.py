import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Cliente, CondicaoPagamento, Empresa, Fornecedor, Transportadora
from .serializers import (
    ClienteSerializer,
    CondicaoPagamentoSerializer,
    EmpresaSerializer,
    FornecedorSerializer,
    TransportadoraSerializer,
)


class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]


class FornecedorViewSet(viewsets.ModelViewSet):
    queryset = Fornecedor.objects.all()
    serializer_class = FornecedorSerializer
    permission_classes = [IsAuthenticated]


class TransportadoraViewSet(viewsets.ModelViewSet):
    queryset = Transportadora.objects.all()
    serializer_class = TransportadoraSerializer
    permission_classes = [IsAuthenticated]


class CondicaoPagamentoViewSet(viewsets.ModelViewSet):
    queryset = CondicaoPagamento.objects.all()
    serializer_class = CondicaoPagamentoSerializer
    permission_classes = [IsAuthenticated]


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
            'bairro': payload.get('bairro', '') or '',
            'cidade': payload.get('localidade', '') or '',
            'uf': payload.get('uf', '') or '',
            'cep': cep_fmt,
        }
    )


@api_view(['GET'])
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
