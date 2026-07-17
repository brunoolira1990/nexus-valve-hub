"""Persistência do campo observacoes no Pedido de Compra."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import PedidoCompra
from apps.produtos.models import FamiliaProduto, Produto


class PedidoCompraObservacoesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pcobs', 'pcobs@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.forn = Fornecedor.objects.create(
            razao_social='Fornecedor Obs Ltda',
            cnpj='22.333.444/0001-55',
        )
        fam = FamiliaProduto.objects.create(
            codigo_figura='FOBS',
            descricao_base='Fam Obs',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao='Item Obs',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-OBS-1',
            unidade='PC',
        )

    def _payload(self, **extra):
        base = {
            'fornecedor_id': self.forn.id,
            'data': '2026-07-15',
            'status': 'Pendente',
            'condicao_pagamento_texto': '30',
            'itens': [
                {
                    'produto_id': self.prod.id,
                    'quantidade': '2',
                    'quantidade_negociada': '2',
                    'valor_unitario': '50.00',
                    'preco_por_unidade_negociada': '50.00',
                    'unidade_negociada': 'PC',
                }
            ],
        }
        base.update(extra)
        return base

    def test_criar_com_observacoes(self):
        res = self.client.post(
            '/api/pedidos-compra/',
            self._payload(observacoes='Linha 1\nLinha 2'),
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()['observacoes'], 'Linha 1\nLinha 2')
        pedido = PedidoCompra.objects.get(pk=res.json()['id'])
        self.assertEqual(pedido.observacoes, 'Linha 1\nLinha 2')

    def test_editar_observacoes(self):
        created = self.client.post('/api/pedidos-compra/', self._payload(observacoes='Inicial'), format='json')
        self.assertEqual(created.status_code, 201, created.content)
        pk = created.json()['id']
        patch = self.client.patch(
            f'/api/pedidos-compra/{pk}/',
            {'observacoes': 'Atualizado\ncom duas linhas'},
            format='json',
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        self.assertEqual(patch.json()['observacoes'], 'Atualizado\ncom duas linhas')

    def test_patch_outro_campo_preserva_observacoes(self):
        created = self.client.post(
            '/api/pedidos-compra/',
            self._payload(observacoes='Manter este texto'),
            format='json',
        )
        self.assertEqual(created.status_code, 201, created.content)
        pk = created.json()['id']
        patch = self.client.patch(
            f'/api/pedidos-compra/{pk}/',
            {'status': 'Aprovado'},
            format='json',
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        self.assertEqual(patch.json()['observacoes'], 'Manter este texto')
        self.assertEqual(patch.json()['status'].upper(), 'APROVADO')

    def test_campo_opcional_vazio(self):
        res = self.client.post('/api/pedidos-compra/', self._payload(), format='json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json().get('observacoes') or '', '')
