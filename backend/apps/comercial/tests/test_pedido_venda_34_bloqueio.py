"""Comercial/NF-e 3.4 — bloqueio de itens do pedido após faturamento."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.comercial.faturamento_pedido_venda import (
    cancelar_faturamento_pedido,
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
)
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.pedido_venda_bloqueio import sincronizar_itens_pedido_venda, validar_atualizacao_itens_pedido_venda
from apps.comercial.serializers import PedidoVendaSerializer
from apps.comercial.tests.test_faturamento_pedido_venda import _pedido_com_itens


class PedidoVendaBloqueio34Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pv34', 'pv34@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _payload_item(self, item: ItemPedidoVenda, **patch) -> dict:
        base = {
            'id': item.id,
            'produto_id': item.produto_id,
            'quantidade': str(item.quantidade),
            'quantidade_negociada': str(item.quantidade_negociada or item.quantidade),
            'valor_unitario': str(item.valor_unitario),
            'preco_por_unidade_negociada': str(item.preco_por_unidade_negociada or item.valor_unitario),
            'desconto': str(item.desconto),
            'unidade_negociada': item.unidade_negociada or 'PC',
        }
        base.update(patch)
        return base

    def test_pedido_aberto_permite_adicionar_item(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('10'))
        payload = {
            'numero': pedido.numero,
            'cliente_id': pedido.cliente_id,
            'data': pedido.data.isoformat(),
            'status': pedido.status,
            'itens': [
                self._payload_item(item),
                {
                    'produto_id': item.produto_id,
                    'quantidade': '2',
                    'quantidade_negociada': '2',
                    'valor_unitario': '10',
                    'preco_por_unidade_negociada': '10',
                    'desconto': '0',
                    'unidade_negociada': 'PC',
                },
            ],
        }
        ser = PedidoVendaSerializer(pedido, data=payload, partial=False)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        self.assertEqual(pedido.itens.count(), 2)

    def test_pedido_faturado_bloqueia_alteracao_itens(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('10'))
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '10'}]},
            usuario=self.user,
        )
        confirmar_faturamento_pedido(pedido, fat['faturamento_id'])
        pedido.refresh_from_db()
        self.assertEqual(pedido.status.upper(), 'FATURADO')

        with self.assertRaises(ValidationError) as ctx:
            validar_atualizacao_itens_pedido_venda(
                pedido,
                [self._payload_item(item, quantidade='9', quantidade_negociada='9')],
            )
        self.assertIn('faturado', str(ctx.exception.detail).lower())

    def test_item_faturado_nao_exclui(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('10'))
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '4'}]},
            usuario=self.user,
        )
        confirmar_faturamento_pedido(pedido, fat['faturamento_id'])
        item.refresh_from_db()
        pedido.refresh_from_db()

        with self.assertRaises(ValidationError):
            validar_atualizacao_itens_pedido_venda(pedido, [])

    def test_item_parcial_nao_reduz_abaixo_faturada(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('10'))
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '4'}]},
            usuario=self.user,
        )
        confirmar_faturamento_pedido(pedido, fat['faturamento_id'])
        item.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            validar_atualizacao_itens_pedido_venda(
                pedido,
                [self._payload_item(item, quantidade='2', quantidade_negociada='2')],
            )
        self.assertIn('faturada', str(ctx.exception.detail).lower())

    def test_item_faturado_nao_troca_produto(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('5'))
        outro_produto_id = item.produto_id + 999
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '5'}]},
            usuario=self.user,
        )
        confirmar_faturamento_pedido(pedido, fat['faturamento_id'])
        item.refresh_from_db()

        with self.assertRaises(ValidationError):
            validar_atualizacao_itens_pedido_venda(
                pedido,
                [self._payload_item(item, produto_id=outro_produto_id)],
            )

    def test_pedido_faturado_pode_salvar_observacao(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('10'))
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '10'}]},
            usuario=self.user,
        )
        confirmar_faturamento_pedido(pedido, fat['faturamento_id'])
        pedido.refresh_from_db()

        resp = self.client.patch(
            f'/api/pedidos-venda/{pedido.pk}/',
            {
                'numero': pedido.numero,
                'cliente_id': pedido.cliente_id,
                'data': pedido.data.isoformat(),
                'status': pedido.status,
                'observacoes_comerciais': 'Observação após faturamento',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        pedido.refresh_from_db()
        self.assertEqual(pedido.observacoes_comerciais, 'Observação após faturamento')

    def test_item_sem_produto_retorna_erro_amigavel(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('2'), preco=Decimal('250'))
        payload = {
            'numero': pedido.numero,
            'cliente_id': pedido.cliente_id,
            'data': pedido.data.isoformat(),
            'status': pedido.status,
            'itens': [
                {
                    'id': item.id,
                    'quantidade': '2',
                    'quantidade_negociada': '2',
                    'valor_unitario': '250',
                    'preco_por_unidade_negociada': '250',
                    'desconto': '0',
                    'unidade_negociada': 'PC',
                }
            ],
        }
        resp = self.client.patch(f'/api/pedidos-venda/{pedido.pk}/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.content)
        msg = str(resp.data).lower()
        self.assertIn('item sem produto', msg)

    def test_patch_parcial_nao_apaga_produto_do_item(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('1'), preco=Decimal('250'))
        payload = {
            'numero': pedido.numero,
            'cliente_id': pedido.cliente_id,
            'data': pedido.data.isoformat(),
            'status': pedido.status,
            'itens': [
                {
                    'id': item.id,
                    'quantidade': '2',
                    'quantidade_negociada': '2',
                    'valor_unitario': '250',
                    'preco_por_unidade_negociada': '250',
                    'desconto': '0',
                    'unidade_negociada': 'PC',
                    'produto_id': item.produto_id,
                }
            ],
        }
        resp = self.client.patch(f'/api/pedidos-venda/{pedido.pk}/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        item.refresh_from_db()
        pedido.refresh_from_db()
        self.assertEqual(item.produto_id, payload['itens'][0]['produto_id'])
        self.assertEqual(item.quantidade_negociada, Decimal('2'))
        self.assertEqual(pedido.valor_total, Decimal('500.00'))

    def test_item_com_faturamento_cancelado_pode_ser_excluido(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('2'))
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '2'}]},
            usuario=self.user,
        )
        cancelar_faturamento_pedido(pedido, fat['faturamento_id'])
        item.refresh_from_db()
        self.assertEqual(item.itens_faturamento.count(), 1)

        validar_atualizacao_itens_pedido_venda(pedido, [])
        sincronizar_itens_pedido_venda(pedido, [])
        pedido.refresh_from_db()
        self.assertEqual(pedido.itens.count(), 0)
        self.assertFalse(item.itens_faturamento.exists())

    def test_item_com_rascunho_faturamento_nao_exclui(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('2'))
        criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '1'}]},
            usuario=self.user,
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_atualizacao_itens_pedido_venda(pedido, [])
        self.assertIn('faturamento vinculado', str(ctx.exception.detail).lower())
