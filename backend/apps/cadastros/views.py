import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.cadastros.consulta_externa import consultar_cep_viacep, format_cep_br, normalizar_cep_digitos
from .models import Cliente, Empresa, Fornecedor, Transportadora
from .serializers import (
    ClienteSerializer,
    EmpresaSerializer,
    FornecedorSerializer,
    TransportadoraSerializer,
)
from django.db.models import Case, Q, When

from nexus_erp.list_mixins import AutocompleteOrPaginationMixin, aplicar_ordering
from nexus_erp.pagination import NexusPageNumberPagination
from nexus_erp.view_mixins import FriendlyDestroyMixin


def _digits_only(s: str) -> str:
    return ''.join(ch for ch in (s or '') if ch.isdigit())


class EmpresaViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def perform_create(self, serializer):
        empresa = serializer.save()
        from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe

        ensure_numeracao_padrao_nfe(empresa)

    @staticmethod
    def _action_validar_certificado_nfe(empresa):
        from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error
        from apps.fiscal.nfe_integracao.services import validar_certificado_empresa

        try:
            return Response(validar_certificado_empresa(empresa))
        except CertificadoA1Error as exc:
            return Response(
                {'valido': False, 'mensagens': [str(exc)], 'erro': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['get'], url_path='validar-certificado-nfe')
    def validar_certificado_nfe(self, request, pk=None):
        """NF-e 3.6 — valida certificado A1/PFX cadastrado na empresa."""
        return self._action_validar_certificado_nfe(self.get_object())

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search),
            )
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'razao_social': 'razao_social', 'cnpj': 'cnpj', 'cidade': 'cidade'},
            'razao_social',
        )


class ClienteViewSet(FriendlyDestroyMixin, AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    destroy_entity_label = 'cliente'
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            digits = _digits_only(search)
            q = (
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search)
                | Q(ie__icontains=search)
            )
            if digits:
                q |= Q(cnpj__icontains=digits)
            qs = qs.filter(q)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'razao_social': 'razao_social', 'cnpj': 'cnpj', 'cidade': 'cidade'},
            'razao_social',
        )


class FornecedorViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Fornecedor.objects.all()
    serializer_class = FornecedorSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    @staticmethod
    def _ranked_search(qs, search: str, limit: int):
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
        if digits:
            q |= Q(cnpj__icontains=digits)
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

    def get_queryset(self):
        qs = Fornecedor.objects.all()
        search = (self.request.query_params.get('search') or '').strip()
        uf = (self.request.query_params.get('uf') or '').strip()
        if uf:
            qs = qs.filter(uf__iexact=uf.upper())
        if search and not (
            (self.request.query_params.get('limit') or '').strip()
            and not (self.request.query_params.get('page') or '').strip()
        ):
            digits = _digits_only(search)
            q = (
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search)
                | Q(telefone__icontains=search)
            )
            if digits:
                q |= Q(cnpj__icontains=digits)
            qs = qs.filter(q)
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'razao_social': 'razao_social', 'cnpj': 'cnpj', 'cidade': 'cidade'},
            'razao_social',
        )

    def list(self, request, *args, **kwargs):
        limit = (request.query_params.get('limit') or '').strip()
        page = (request.query_params.get('page') or '').strip()
        search = (request.query_params.get('search') or '').strip()
        if limit and not page:
            try:
                n = max(1, min(int(limit), 100))
            except (TypeError, ValueError):
                n = 20
            qs = Fornecedor.objects.all()
            uf = (request.query_params.get('uf') or '').strip()
            if uf:
                qs = qs.filter(uf__iexact=uf.upper())
            if search:
                qs = self._ranked_search(qs, search, n)
            else:
                qs = qs.order_by('razao_social')[:n]
            return Response(FornecedorSerializer(qs, many=True).data)
        return super().list(request, *args, **kwargs)


class TransportadoraViewSet(AutocompleteOrPaginationMixin, viewsets.ModelViewSet):
    queryset = Transportadora.objects.all()
    serializer_class = TransportadoraSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NexusPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            digits = _digits_only(search)
            q = (
                Q(razao_social__icontains=search)
                | Q(nome_fantasia__icontains=search)
                | Q(cnpj__icontains=search)
                | Q(cidade__icontains=search)
                | Q(placa_padrao__icontains=search)
                | Q(ie__icontains=search)
            )
            if digits:
                q |= Q(cnpj__icontains=digits)
            if search.isdigit():
                q |= Q(pk=int(search))
            qs = qs.filter(q)
        uf = (self.request.query_params.get('uf') or '').strip()
        if uf:
            qs = qs.filter(uf__iexact=uf.upper())
        return aplicar_ordering(
            qs,
            self.request.query_params.get('ordering'),
            {'razao_social': 'razao_social', 'cnpj': 'cnpj', 'cidade': 'cidade'},
            'razao_social',
        )


def _get_json(url: str, timeout: int = 8) -> dict:
    request = Request(url, headers={"User-Agent": "NEXUS-APP/1.0"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("Resposta inválida do serviço externo.") from e


from apps.cadastros.consulta_externa import consultar_cep_viacep, format_cep_br, normalizar_cep_digitos


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def consulta_cep(request, cep: str):
    cep_digitos = normalizar_cep_digitos(cep)
    if len(cep_digitos) != 8:
        return Response({'detail': 'CEP inválido. Informe 8 dígitos.'}, status=status.HTTP_400_BAD_REQUEST)

    data = consultar_cep_viacep(cep_digitos)
    if not data:
        return Response(
            {'detail': 'CEP não encontrado ou falha na consulta.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(data)


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
    cep_fmt = format_cep_br(cep_raw) if len(cep_raw) == 8 and cep_raw.isdigit() else (payload.get('cep') or '')

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
