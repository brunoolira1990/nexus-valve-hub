"""ERP 4.0.13.6 — cadastro rápido comercial/compras + quantidade editável no Pedido de Venda."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.converter_proposta_pedido import converter_proposta_em_pedido_venda
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda, ItemProposta, PedidoVenda
from apps.comercial.pedido_venda_bloqueio import validar_atualizacao_itens_pedido_venda
from apps.comercial.serializers import PedidoVendaSerializer
from apps.comercial.tests.test_converter_proposta_pedido import (
    _item,
    _produto,
    _proposta_aprovada,
)
from apps.comercial.tests.test_faturamento_pedido_venda import _pedido_com_itens
from apps.cadastros.utils import validar_cnpj
from apps.produtos.models import Produto


def _cnpj_valido() -> str:
    """CNPJ com dígitos verificadores válidos para POST na API."""
    for _ in range(40):
        base = f'{uuid.uuid4().int % 10_000_000_000_000:012d}'
        if base == base[0] * 12:
            continue
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        d1 = sum(int(base[i]) * pesos1[i] for i in range(12))
        d1 = 0 if d1 % 11 < 2 else 11 - (d1 % 11)
        parcial = base + str(d1)
        d2 = sum(int(parcial[i]) * pesos2[i] for i in range(13))
        d2 = 0 if d2 % 11 < 2 else 11 - (d2 % 11)
        cnpj = f'{base}{d1}{d2}'
        if validar_cnpj(cnpj):
            return (
                f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}'
            )
    return '03.476.382/0001-00'


class Comercial40136CadastroRapidoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('40136', '40136@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_criar_cliente_rapido_via_api(self):
        cnpj = _cnpj_valido()
        resp = self.client.post(
            '/api/clientes/',
            {
                'razao_social': 'Cliente Rápido 40136',
                'nome_fantasia': 'CR40136',
                'cnpj': cnpj,
                'uf': 'SP',
                'cidade': 'São Paulo',
                'ativo': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data['razao_social'].upper(), 'CLIENTE RÁPIDO 40136')
        self.assertTrue(Cliente.objects.filter(cnpj=cnpj).exists())

    def test_nao_duplica_cliente_por_cnpj(self):
        cnpj = _cnpj_valido()
        Cliente.objects.create(razao_social='Existente', cnpj=cnpj, uf='SP')
        resp = self.client.post(
            '/api/clientes/',
            {'razao_social': 'Outro', 'cnpj': cnpj, 'uf': 'SP', 'ativo': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.content)

    def test_criar_fornecedor_rapido_via_api(self):
        cnpj = _cnpj_valido()
        resp = self.client.post(
            '/api/fornecedores/',
            {
                'razao_social': 'Fornecedor Rápido 40136',
                'cnpj': cnpj,
                'uf': 'RJ',
                'cidade': 'Rio',
                'ativo': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertTrue(Fornecedor.objects.filter(cnpj=cnpj).exists())

    def test_nao_duplica_fornecedor_por_cnpj(self):
        cnpj = _cnpj_valido()
        Fornecedor.objects.create(razao_social='Forn Existente', cnpj=cnpj, uf='RJ')
        resp = self.client.post(
            '/api/fornecedores/',
            {'razao_social': 'Outro Forn', 'cnpj': cnpj, 'uf': 'RJ', 'ativo': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.content)

    def test_criar_produto_rapido_manual_com_material(self):
        suf = uuid.uuid4().hex[:6].upper()
        resp = self.client.post(
            '/api/produtos/',
            {
                'modo_codigo': 'MANUAL',
                'codigo_completo': f'Q40136-{suf}',
                'descricao': 'Produto cadastro rápido',
                'unidade': 'PC',
                'ncm': '73079300',
                'material': 'ACO CARBONO',
                'preco_venda': '100.00',
                'preco_custo': '50.00',
                'estoque_minimo': '0',
                'ativo': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data['material'], 'ACO CARBONO')
        self.assertEqual(resp.data['material_label'], 'Aço Carbono')


class Comercial40136QuantidadePedidoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('40136q', '40136q@test.com', 'x')
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

    def test_pedido_aberto_permite_alterar_quantidade(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('1'))
        payload = {
            'numero': pedido.numero,
            'cliente_id': pedido.cliente_id,
            'data': pedido.data.isoformat(),
            'status': pedido.status,
            'itens': [self._payload_item(item, quantidade='10', quantidade_negociada='10')],
        }
        ser = PedidoVendaSerializer(pedido, data=payload, partial=False)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        item.refresh_from_db()
        self.assertEqual(item.quantidade_negociada, Decimal('10'))
        self.assertEqual(item.quantidade, Decimal('10'))

    def test_quantidade_zero_rejeitada(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('5'))
        payload = {
            'numero': pedido.numero,
            'cliente_id': pedido.cliente_id,
            'data': pedido.data.isoformat(),
            'status': pedido.status,
            'itens': [self._payload_item(item, quantidade='0', quantidade_negociada='0')],
        }
        ser = PedidoVendaSerializer(pedido, data=payload, partial=False)
        self.assertFalse(ser.is_valid())
        # ItemPedidoVendaSerializer valida quantidade antes de quantidade_negociada;
        # com ambos zero no payload, o erro reportado é em quantidade.
        self.assertIn('quantidade', ser.errors.get('itens', [{}])[0])

    def test_pedido_faturado_bloqueia_alteracao_quantidade(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('10'))
        fat = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '10'}]},
            usuario=self.user,
        )
        confirmar_faturamento_pedido(pedido, fat['faturamento_id'])
        pedido.refresh_from_db()

        with self.assertRaises(ValidationError):
            validar_atualizacao_itens_pedido_venda(
                pedido,
                [self._payload_item(item, quantidade='5', quantidade_negociada='5')],
            )

    def test_quantidade_nao_forcada_para_um_ao_salvar(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('7'))
        resp = self.client.patch(
            f'/api/pedidos-venda/{pedido.pk}/',
            {
                'numero': pedido.numero,
                'cliente_id': pedido.cliente_id,
                'data': pedido.data.isoformat(),
                'status': pedido.status,
                'itens': [self._payload_item(item, quantidade='7', quantidade_negociada='7')],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        item.refresh_from_db()
        self.assertEqual(item.quantidade_negociada, Decimal('7'))

    def test_proposta_quantidade_dez_vira_pedido_quantidade_dez(self):
        proposta = _proposta_aprovada()
        prod = _produto()
        ItemProposta.objects.filter(proposta=proposta).delete()
        ItemProposta.objects.create(
            proposta=proposta,
            produto=prod,
            quantidade=Decimal('10'),
            quantidade_negociada=Decimal('10'),
            valor_unitario=Decimal('500'),
            preco_por_unidade_negociada=Decimal('500'),
            desconto=Decimal('0'),
            modo_preco='sugerido',
            icms_saida_percentual=Decimal('18'),
            pis_saida_percentual=Decimal('1.65'),
            cofins_saida_percentual=Decimal('7.6'),
        )
        r = converter_proposta_em_pedido_venda(proposta)
        pv_item = ItemPedidoVenda.objects.get(pedido_id=r['pedido_id'])
        self.assertEqual(pv_item.quantidade_negociada, Decimal('10'))
        self.assertEqual(pv_item.quantidade, Decimal('10'))

    def test_total_item_recalcula_apos_quantidade(self):
        pedido, item = _pedido_com_itens(qtd=Decimal('2'), preco=Decimal('100'))
        payload = {
            'numero': pedido.numero,
            'cliente_id': pedido.cliente_id,
            'data': pedido.data.isoformat(),
            'status': pedido.status,
            'itens': [self._payload_item(item, quantidade='4', quantidade_negociada='4')],
        }
        ser = PedidoVendaSerializer(pedido, data=payload, partial=False)
        self.assertTrue(ser.is_valid(), ser.errors)
        instance = ser.save()
        self.assertEqual(instance.valor_total, Decimal('400'))
