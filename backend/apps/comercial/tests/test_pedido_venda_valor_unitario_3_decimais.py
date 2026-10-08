"""Precisão do valor unitário do Pedido de Venda (até 3 casas)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.comercial.valor_unitario_precisao import (
    MSG_VALOR_UNITARIO_MAX_3_CASAS,
    casas_decimais_significativas,
    validar_max_casas_valor_unitario,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'P{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod PV',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PV-{suf}',
        unidade='PC',
        ncm='84818200',
    )


class ValorUnitarioPrecisaoHelperTests(TestCase):
    def test_casas_e_validacao(self):
        self.assertEqual(casas_decimais_significativas(Decimal('10')), 0)
        self.assertEqual(casas_decimais_significativas(Decimal('10.5')), 1)
        self.assertEqual(casas_decimais_significativas(Decimal('10.25')), 2)
        self.assertEqual(casas_decimais_significativas(Decimal('10.125')), 3)
        self.assertEqual(casas_decimais_significativas(Decimal('10.1250')), 3)
        self.assertEqual(casas_decimais_significativas(Decimal('0.001')), 3)
        self.assertEqual(validar_max_casas_valor_unitario('10.125'), Decimal('10.125'))
        with self.assertRaises(ValueError) as ctx:
            validar_max_casas_valor_unitario('10.1255')
        self.assertIn('3 casas', str(ctx.exception))


class PedidoVendaValorUnitarioTresDecimaisTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pv3d', 'pv3d@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
        self.cli = Cliente.objects.create(
            razao_social='Cli',
            cnpj=_cnpj(),
            uf='RJ',
            cidade='Rio',
            cep='20040-020',
            logradouro='Rua A',
            numero='1',
            bairro='Centro',
        )
        self.prod = _produto()

    def _criar_pedido(self, preco: str, qtd: str = '3'):
        payload = {
            'numero': f'PV-{uuid.uuid4().hex[:8].upper()}',
            'empresa_emitente_id': self.emp.pk,
            'cliente_id': self.cli.pk,
            'data': date.today().isoformat(),
            'status': 'ABERTO',
            'itens': [
                {
                    'produto_id': self.prod.pk,
                    'quantidade': qtd,
                    'quantidade_negociada': qtd,
                    'unidade_negociada': 'PC',
                    'preco_por_unidade_negociada': preco,
                    'valor_unitario': preco,
                    'desconto': '0',
                    'snapshot_fiscal': {'ncm': '84818200', 'cfop': '5102'},
                },
            ],
        }
        return self.client.post('/api/pedidos-venda/', payload, format='json')

    def test_cria_e_reabre_10_125(self):
        r = self._criar_pedido('10.125', '3')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        pedido_id = r.json()['id']
        item = ItemPedidoVenda.objects.get(pedido_id=pedido_id)
        self.assertEqual(item.preco_por_unidade_negociada, Decimal('10.1250'))
        # Espelho legado permanece em 2 casas no banco.
        self.assertEqual(item.valor_unitario, Decimal('10.13'))

        det = self.client.get(f'/api/pedidos-venda/{pedido_id}/').json()
        preco = Decimal(str(det['itens'][0]['preco_por_unidade_negociada']))
        self.assertEqual(preco, Decimal('10.1250'))
        # Total monetário: 3 * 10.125 = 30.375 → 30.38
        self.assertEqual(Decimal(str(det['valor_total'])), Decimal('30.38'))

    def test_editar_preserva_10_125(self):
        r = self._criar_pedido('10.125')
        pedido_id = r.json()['id']
        item_id = r.json()['itens'][0]['id']
        patch = {
            'itens': [
                {
                    'id': item_id,
                    'produto_id': self.prod.pk,
                    'quantidade': '3',
                    'quantidade_negociada': '3',
                    'unidade_negociada': 'PC',
                    'preco_por_unidade_negociada': '10.125',
                    'valor_unitario': '10.125',
                    'desconto': '0',
                },
            ],
        }
        r2 = self.client.patch(f'/api/pedidos-venda/{pedido_id}/', patch, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.content)
        item = ItemPedidoVenda.objects.get(pk=item_id)
        self.assertEqual(item.preco_por_unidade_negociada, Decimal('10.1250'))

    def test_aceita_0_001_e_duas_casas(self):
        r1 = self._criar_pedido('0.001', '1')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.content)
        self.assertEqual(
            ItemPedidoVenda.objects.get(pedido_id=r1.json()['id']).preco_por_unidade_negociada,
            Decimal('0.0010'),
        )
        r2 = self._criar_pedido('10.25', '1')
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.content)

    def test_rejeita_quatro_casas(self):
        r = self._criar_pedido('10.1255')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        body = str(r.json())
        self.assertIn('3 casas', body)

    def test_faturamento_preserva_preco(self):
        r = self._criar_pedido('10.125', '4')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        pedido = PedidoVenda.objects.get(pk=r.json()['id'])
        item = pedido.itens.get()
        criado = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]},
        )
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        linha = fat.itens.get()
        self.assertEqual(linha.valor_unitario, Decimal('10.1250'))
        self.assertEqual(linha.valor_total, Decimal('20.25'))  # 2 * 10.125 = 20.25 exact
