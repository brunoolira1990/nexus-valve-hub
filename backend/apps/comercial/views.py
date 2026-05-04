from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from . import pricing as price_rules
from .observed_metrics import (
    montar_apoio_gerencial,
    montar_referencia_comercial_custo_compra,
    montar_referencia_comercial_frete,
)
from .models import PedidoCompra, PedidoVenda, Proposta
from .serializers import PedidoCompraSerializer, PedidoVendaSerializer, PropostaSerializer


class PropostaViewSet(viewsets.ModelViewSet):
    queryset = (
        Proposta.objects.select_related('cliente', 'empresa_emitente')
        .prefetch_related('itens__produto')
        .all()
    )
    serializer_class = PropostaSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('-id')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente__nome_fantasia__icontains=search)
                | Q(cliente_avulso_nome__icontains=search),
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs

    @action(detail=False, methods=['get'], url_path='apoio-gerencial')
    def apoio_gerencial(self, request):
        try:
            result = montar_apoio_gerencial(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-frete')
    def referencia_comercial_frete(self, request):
        try:
            result = montar_referencia_comercial_frete(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-custo-compra')
    def referencia_comercial_custo_compra(self, request):
        try:
            result = montar_referencia_comercial_custo_compra(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=True, methods=['post'], url_path='converter-pedido')
    def converter_pedido(self, request, pk=None):
        proposta = self.get_object()

        if PedidoVenda.objects.filter(proposta=proposta).exists():
            return Response(
                {'detail': 'Esta proposta já foi convertida em pedido de venda.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not proposta.cliente_id:
            return Response(
                {'detail': 'Vincule um cliente cadastrado para converter a proposta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for item in proposta.itens.all():
            if item.produto_id:
                continue
            if not price_rules.ncm_fiscal_valido(item.ncm_avulso or ''):
                return Response(
                    {
                        'detail': (
                            'Existem itens avulsos sem NCM válido (8 dígitos). '
                            'Informe o NCM para simulação fiscal ou regularize o item antes de converter em pedido.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if proposta.itens.filter(produto__isnull=True).exists():
            return Response(
                {
                    'detail': (
                        'Vincule todos os itens avulsos a produtos cadastrados antes de converter. '
                        'O pedido e o faturamento exigem produto no cadastro; o NCM do item avulso serve para simulação até essa regularização.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        numero_base = f"PV-{proposta.numero}"
        numero = numero_base
        suffix = 2
        while PedidoVenda.objects.filter(numero=numero).exists():
            numero = f"{numero_base}-{suffix}"
            suffix += 1

        itens_payload = [
            {
                'produto_id': item.produto_id,
                'quantidade': item.quantidade,
                'valor_unitario': item.valor_unitario,
                'unidade_negociada': item.unidade_negociada,
                'quantidade_negociada': item.quantidade_negociada,
                'unidade_estoque_calculada': item.unidade_estoque_calculada,
                'quantidade_estoque_calculada': item.quantidade_estoque_calculada,
                'peso_total_kg': item.peso_total_kg,
                'metros_total': item.metros_total,
                'barras_total': item.barras_total,
                'preco_por_unidade_negociada': item.preco_por_unidade_negociada,
                'preco_por_kg': item.preco_por_kg,
                'preco_por_metro': item.preco_por_metro,
                'fator_conversao': item.fator_conversao,
                'corrida_id': None,
            }
            for item in proposta.itens.all()
        ]

        payload = {
            'numero': numero,
            'empresa_emitente_id': proposta.empresa_emitente_id,
            'cliente_id': proposta.cliente_id,
            'data': proposta.data.isoformat(),
            'status': 'Pendente',
            'condicao_pagamento_texto': proposta.condicao_pagamento_texto,
            'dias_parcelas': proposta.dias_parcelas,
            'quantidade_parcelas': proposta.quantidade_parcelas,
            'vencimentos_previstos': [d.isoformat() for d in proposta.vencimentos_previstos],
            'valor_total': proposta.valor_total,
            'proposta_id': proposta.id,
            'itens': itens_payload,
        }

        serializer = PedidoVendaSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            pedido = serializer.save()
        return Response(PedidoVendaSerializer(pedido).data, status=status.HTTP_201_CREATED)


class PedidoVendaViewSet(viewsets.ModelViewSet):
    queryset = (
        PedidoVenda.objects.select_related('cliente', 'proposta', 'empresa_emitente')
        .prefetch_related('itens__produto', 'itens__corrida')
        .all()
    )
    serializer_class = PedidoVendaSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('-id')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(cliente__razao_social__icontains=search)
                | Q(cliente__nome_fantasia__icontains=search)
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs

    @action(detail=False, methods=['get'], url_path='apoio-gerencial')
    def apoio_gerencial(self, request):
        try:
            result = montar_apoio_gerencial(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-frete')
    def referencia_comercial_frete(self, request):
        try:
            result = montar_referencia_comercial_frete(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)

    @action(detail=False, methods=['get'], url_path='referencia-comercial-custo-compra')
    def referencia_comercial_custo_compra(self, request):
        try:
            result = montar_referencia_comercial_custo_compra(request.query_params)
        except Exception as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(result.payload)


class PedidoCompraViewSet(viewsets.ModelViewSet):
    queryset = PedidoCompra.objects.select_related('fornecedor').prefetch_related('itens__produto').all()
    serializer_class = PedidoCompraSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('-id')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search)
                | Q(fornecedor__razao_social__icontains=search)
                | Q(fornecedor__nome_fantasia__icontains=search)
                | Q(fornecedor__cnpj__icontains=search)
            )
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                pass
        return qs
