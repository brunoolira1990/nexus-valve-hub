"""Rota GET /api/pedidos-compra/<id>/pdf/ e corpo PDF (ReportLab)."""

import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import PedidoCompra
from apps.comercial.pedido_compra_pdf import gerar_pedido_compra_pdf_bytes
from apps.comercial.serializers import PedidoCompraSerializer
from pypdf import PdfReader
from apps.produtos.models import FamiliaProduto, Produto


class PedidoCompraPdfRouteTests(TestCase):
    def test_url_resolve(self):
        m = resolve('/api/pedidos-compra/99/pdf/')
        self.assertEqual(m.url_name, 'pedidocompra-pdf')
        self.assertEqual(m.kwargs.get('pk'), 99)

    def test_reverse(self):
        self.assertEqual(reverse('pedidocompra-pdf', kwargs={'pk': 1}), '/api/pedidos-compra/1/pdf/')


class PedidoCompraPdfResponseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pdf_user', 'pdf@test.com', 'secret123')
        self.forn = Fornecedor.objects.create(
            razao_social='Fornecedor PDF Ltda',
            nome_fantasia='PDF Forn',
            cnpj='11.222.333/0001-81',
            observacoes='Nota cadastral fornecedor',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FTPDF',
            descricao_base='Família PDF',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao='Item PDF',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-PDF-1',
            unidade='PC',
        )
        ser = PedidoCompraSerializer(
            data={
                'fornecedor_id': self.forn.id,
                'data': '2026-05-13',
                'status': 'Pendente',
                'condicao_pagamento_texto': '30',
                'prazo_entrega_texto': '15 dias',
                'observacoes': 'Observação do pedido',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '10.00',
                        'preco_por_unidade_negociada': '10.00',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.pedido: PedidoCompra = ser.save()

    def test_get_pdf_200_and_bytes(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('pedidocompra-pdf', kwargs={'pk': self.pedido.pk})
        resp = c.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp.content[:200]))
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('no-store', (resp.get('Cache-Control') or '').lower())
        cdisp = resp['Content-Disposition']
        self.assertIn('inline', cdisp)
        self.assertIn('pedido-compra-', cdisp)
        self.assertIn('.pdf', cdisp)
        self.assertTrue(resp.content.startswith(b'%PDF'), resp.content[:20])

    def test_pdf_single_item_fits_one_page(self):
        """Layout compacto: pedido simples não deve estourar A4 por espaçamento excessivo."""
        pdf_bytes = gerar_pedido_compra_pdf_bytes(self.pedido)
        n = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
        self.assertEqual(n, 1, f'esperado 1 página, obtido {n}')
