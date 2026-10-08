"""Numeração automática PC-AAAAMMDD-NNNN e imutabilidade do número."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.serializers import PedidoCompraSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _slug() -> str:
    return uuid.uuid4().hex[:8]


class PedidoCompraNumeroTests(TestCase):
    def setUp(self):
        s = _slug()
        self.forn = Fornecedor.objects.create(
            razao_social=f'Fornecedor Teste {s}',
            cnpj='11.222.333/0001-81',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura=f'FT{s}'[:16],
            descricao_base=f'Família teste {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao=f'Produto teste {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'PR-{s}',
            unidade='PC',
        )

    def _item_payload(self):
        return [
            {
                'produto_id': self.prod.id,
                'quantidade': '10',
                'quantidade_negociada': '10',
                'valor_unitario': '50.00',
                'preco_por_unidade_negociada': '50.00',
                'unidade_negociada': 'PC',
            }
        ]

    def _payload(self, data_iso: str, numero: str | None = None):
        p = {
            'fornecedor_id': self.forn.id,
            'data': data_iso,
            'status': 'Pendente',
            'condicao_pagamento_texto': '30',
            'itens': self._item_payload(),
        }
        if numero is not None:
            p['numero'] = numero
        return p

    def test_payload_sem_chave_numero_e_valido(self):
        payload = self._payload('2026-06-01')
        self.assertNotIn('numero', payload)
        ser = PedidoCompraSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_api_post_201_sem_numero(self):
        user = get_user_model().objects.create_user('pc_num', 'pc_num@test.com', 'secret123')
        client = APIClient()
        client.force_authenticate(user=user)
        body = {
            'fornecedor_id': self.forn.id,
            'data': '2026-06-15',
            'status': 'Pendente',
            'condicao_pagamento_texto': '30',
            'itens': self._item_payload(),
        }
        self.assertNotIn('numero', body)
        resp = client.post(reverse('pedidocompra-list'), body, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertRegex(resp.data.get('numero', ''), r'^PC-20260615-\d{4}$')

    def test_create_sem_numero_gera_pc(self):
        ser = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        self.assertEqual(pedido.numero, 'PC-20260513-0001')

    def test_sequencia_mesmo_dia(self):
        ser1 = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser1.is_valid(), ser1.errors)
        p1 = ser1.save()
        ser2 = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser2.is_valid(), ser2.errors)
        p2 = ser2.save()
        self.assertEqual(p1.numero, 'PC-20260513-0001')
        self.assertEqual(p2.numero, 'PC-20260513-0002')

    def test_sequencia_outro_dia_reinicia(self):
        ser1 = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser1.is_valid(), ser1.errors)
        ser1.save()
        ser2 = PedidoCompraSerializer(data=self._payload('2026-05-14'))
        self.assertTrue(ser2.is_valid(), ser2.errors)
        p2 = ser2.save()
        self.assertEqual(p2.numero, 'PC-20260514-0001')

    def test_editar_data_nao_muda_numero(self):
        ser = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        orig = pedido.numero
        ser_u = PedidoCompraSerializer(
            instance=pedido,
            data={
                'fornecedor_id': self.forn.id,
                'data': '2026-05-20',
                'status': 'Pendente',
                'condicao_pagamento_texto': '30',
                'itens': self._item_payload(),
                'numero': 'PC-20999999-9999',
            },
            partial=True,
        )
        self.assertTrue(ser_u.is_valid(), ser_u.errors)
        ser_u.save()
        pedido.refresh_from_db()
        self.assertEqual(pedido.numero, orig)
        self.assertEqual(pedido.data.isoformat(), '2026-05-20')

    def test_nao_persiste_numero_vazio(self):
        """Campo numero no POST é ignorado (read-only); geração segue a sequência."""
        ser = PedidoCompraSerializer(data=self._payload('2026-05-13', ''))
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        self.assertTrue(pedido.numero.startswith('PC-20260513-'))

    def test_numero_explicito_no_post_e_ignorado(self):
        """Cliente não pode fixar número: valor enviado não substitui a sequência automática."""
        ser1 = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser1.is_valid(), ser1.errors)
        ser1.save()
        ser2 = PedidoCompraSerializer(
            data={
                **self._payload('2026-05-13'),
                'numero': 'PC-20260513-0001',
            }
        )
        self.assertTrue(ser2.is_valid(), ser2.errors)
        p2 = ser2.save()
        self.assertEqual(p2.numero, 'PC-20260513-0002')

    def test_integrity_numero_traduzido_para_validation(self):
        ser1 = PedidoCompraSerializer(data=self._payload('2026-05-13'))
        self.assertTrue(ser1.is_valid(), ser1.errors)
        ser1.save()
        from unittest.mock import patch

        from rest_framework.serializers import ValidationError as DRFValidationError

        with patch('apps.comercial.serializers.alocar_numero_pedido_compra', return_value='PC-20260513-0001'):
            ser2 = PedidoCompraSerializer(data=self._payload('2026-05-13'))
            self.assertTrue(ser2.is_valid(), ser2.errors)
            with self.assertRaises(DRFValidationError) as ctx:
                ser2.save()
            self.assertIn('numero', ctx.exception.detail)
