from datetime import date

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cadastros.models import Fornecedor

from .cotacao_fornecedor_permissions import (
    PodeCancelarCotacaoFornecedor,
    PodeGerenciarCotacaoFornecedor,
    PodeRegistrarRespostaCotacaoFornecedor,
    PodeSelecionarReferenciaCotacaoFornecedor,
    PodeVerCotacaoFornecedor,
)
from .cotacao_fornecedor_serializers import (
    CotacaoFornecedorCreateSerializer,
    CotacaoFornecedorItemInputSerializer,
    CotacaoFornecedorItemSerializer,
    CotacaoFornecedorHistoricoSerializer,
    CotacaoFornecedorParticipanteSerializer,
    CotacaoFornecedorRespostaInputSerializer,
    CotacaoFornecedorRespostaItemSerializer,
    CotacaoFornecedorSerializer,
)
from .cotacao_fornecedor_service import (
    _evento,
    adicionar_item,
    adicionar_participante,
    cancelar_cotacao,
    registrar_resposta,
    selecionar_referencia,
)
from .models import (
    CotacaoFornecedor,
    CotacaoFornecedorItem,
    CotacaoFornecedorParticipante,
    CotacaoFornecedorRespostaItem,
    CotacaoFornecedorHistorico,
)


class CotacaoFornecedorViewSet(viewsets.ModelViewSet):
    queryset = CotacaoFornecedor.objects.select_related('proposta', 'responsavel').prefetch_related(
        'itens__produto',
        Prefetch('participantes', queryset=CotacaoFornecedorParticipante.objects.select_related('fornecedor').prefetch_related('respostas')),
    )
    permission_classes = [IsAuthenticated, PodeVerCotacaoFornecedor]

    def get_serializer_class(self):
        if self.action == 'create':
            return CotacaoFornecedorCreateSerializer
        return CotacaoFornecedorSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'comparativo'):
            classes = [IsAuthenticated, PodeVerCotacaoFornecedor]
        elif self.action in ('respostas',):
            classes = [IsAuthenticated, PodeRegistrarRespostaCotacaoFornecedor]
        elif self.action in ('selecionar_referencia',):
            classes = [IsAuthenticated, PodeSelecionarReferenciaCotacaoFornecedor]
        elif self.action in ('cancelar',):
            classes = [IsAuthenticated, PodeCancelarCotacaoFornecedor]
        else:
            classes = [IsAuthenticated, PodeGerenciarCotacaoFornecedor]
        return [cls() for cls in classes]

    def get_queryset(self):
        qs = super().get_queryset()
        proposta_id = self.request.query_params.get('proposta_id')
        if proposta_id and str(proposta_id).isdigit():
            qs = qs.filter(proposta_id=int(proposta_id))
        status_f = (self.request.query_params.get('status') or '').strip().upper()
        if status_f:
            qs = qs.filter(status=status_f)
        return qs.order_by('-data', '-id')

    def _novo_numero(self):
        prefixo = f'CF-{timezone.localdate().strftime("%Y%m%d")}-'
        ultimo = CotacaoFornecedor.objects.filter(numero__startswith=prefixo).order_by('-id').values_list('numero', flat=True).first()
        try:
            sequencia = int((ultimo or '').rsplit('-', 1)[-1]) + 1
        except (TypeError, ValueError):
            sequencia = 1
        return f'{prefixo}{sequencia:04d}'

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposta = serializer.validated_data.get('proposta')
        cotacao = CotacaoFornecedor.objects.create(
            numero=self._novo_numero(),
            proposta=proposta,
            data=serializer.validated_data.get('data') or date.today(),
            responsavel=request.user,
            prazo_resposta=serializer.validated_data.get('prazo_resposta'),
            observacao=serializer.validated_data.get('observacao', ''),
        )
        _evento(cotacao, 'COTACAO_CRIADA', 'cotação criada', request.user)
        output = CotacaoFornecedorSerializer(cotacao, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='itens')
    def adicionar_item_action(self, request, pk=None):
        cotacao = self.get_object()
        serializer = CotacaoFornecedorItemInputSerializer(data=request.data, context={'proposta_id': cotacao.proposta_id})
        serializer.is_valid(raise_exception=True)
        try:
            item = adicionar_item(
                cotacao,
                serializer.validated_data.get('item_proposta_id').pk if serializer.validated_data.get('item_proposta_id') else None,
                serializer.validated_data.get('quantidade'),
                serializer.validated_data.get('observacao_tecnica', ''),
                request.user,
                produto=serializer.validated_data.get('produto_id'),
                descricao_item=serializer.validated_data.get('descricao_item', ''),
                unidade=serializer.validated_data.get('unidade', ''),
            )
        except (ValueError, TypeError, CotacaoFornecedorItem.DoesNotExist) as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(CotacaoFornecedorItemSerializer(item, context={'proposta_id': cotacao.proposta_id}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'itens/(?P<item_id>[^/.]+)')
    def remover_item_action(self, request, pk=None, item_id=None):
        cotacao = self.get_object()
        try:
            item = cotacao.itens.get(pk=item_id)
        except CotacaoFornecedorItem.DoesNotExist as exc:
            raise ValidationError({'detail': 'Item não encontrado na cotação.'}) from exc
        if item.respostas.exists():
            raise ValidationError({'detail': 'Item com respostas não pode ser removido; preserve o histórico.'})
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='participantes')
    def adicionar_participante_action(self, request, pk=None):
        cotacao = self.get_object()
        try:
            fornecedor = Fornecedor.objects.get(pk=request.data.get('fornecedor_id'), ativo=True)
            participante = adicionar_participante(cotacao, fornecedor, request.user)
        except (Fornecedor.DoesNotExist, ValueError, TypeError) as exc:
            raise ValidationError({'detail': str(exc) if not isinstance(exc, Fornecedor.DoesNotExist) else 'Fornecedor não encontrado ou inativo.'}) from exc
        return Response(CotacaoFornecedorParticipanteSerializer(participante).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'participantes/(?P<participante_id>[^/.]+)')
    def remover_participante_action(self, request, pk=None, participante_id=None):
        cotacao = self.get_object()
        try:
            participante = cotacao.participantes.get(pk=participante_id)
        except CotacaoFornecedorParticipante.DoesNotExist as exc:
            raise ValidationError({'detail': 'Participante não encontrado na cotação.'}) from exc
        if participante.respostas.exists():
            raise ValidationError({'detail': 'Participante com respostas não pode ser removido; preserve o histórico.'})
        participante.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='respostas')
    def respostas(self, request, pk=None):
        cotacao = self.get_object()
        payload = dict(request.data)
        payload['participante'] = payload.get('participante_id', payload.get('participante'))
        payload['cotacao_item'] = payload.get('cotacao_item_id', payload.get('cotacao_item'))
        serializer = CotacaoFornecedorRespostaInputSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        participante = serializer.validated_data['participante']
        item = serializer.validated_data['cotacao_item']
        if participante.cotacao_id != cotacao.pk or item.cotacao_id != cotacao.pk:
            raise ValidationError({'detail': 'Resposta fora da cotação informada.'})
        resposta = registrar_resposta(participante=participante, cotacao_item=item, dados=serializer.validated_data, usuario=request.user)
        return Response(CotacaoFornecedorRespostaItemSerializer(resposta).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='comparativo')
    def comparativo(self, request, pk=None):
        cotacao = self.get_object()
        rows = []
        for item in cotacao.itens.all():
            rows.append({
                'cotacao_item_id': item.pk,
                'item_proposta_id': item.item_proposta_id,
                'produto_id': item.produto_id,
                'descricao': item.descricao_item or (item.produto_snapshot or {}).get('descricao', '') or getattr(item.produto, 'descricao', '') or (f'Item da Proposta #{item.item_proposta_id}' if item.item_proposta_id else ''),
                'unidade': item.unidade,
                'quantidade': item.quantidade,
                'respostas': CotacaoFornecedorRespostaItemSerializer(item.respostas.select_related('participante__fornecedor', 'selecionada_por'), many=True).data,
            })
        return Response({'cotacao_id': cotacao.pk, 'numero': cotacao.numero, 'status': cotacao.status, 'proposta_id': cotacao.proposta_id, 'itens': rows})

    @action(detail=True, methods=['get'], url_path='historico')
    def historico(self, request, pk=None):
        cotacao = self.get_object()
        eventos = cotacao.historico.select_related('usuario').all()
        return Response(CotacaoFornecedorHistoricoSerializer(eventos, many=True).data)

    @action(detail=True, methods=['post'], url_path='selecionar-referencia')
    def selecionar_referencia_action(self, request, pk=None):
        cotacao = self.get_object()
        try:
            resposta = CotacaoFornecedorRespostaItem.objects.select_related('cotacao_item__cotacao').get(pk=request.data.get('resposta_id'), cotacao_item__cotacao=cotacao)
            resposta = selecionar_referencia(resposta=resposta, usuario=request.user)
        except CotacaoFornecedorRespostaItem.DoesNotExist as exc:
            raise ValidationError({'detail': 'Resposta não encontrada nesta cotação.'}) from exc
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response(CotacaoFornecedorRespostaItemSerializer(resposta).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        cotacao = cancelar_cotacao(self.get_object(), request.user)
        return Response(CotacaoFornecedorSerializer(cotacao, context={'request': request}).data)
