"""Comercial 2.6.2 — Content-Disposition com filename nos PDFs comerciais."""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.comercial.serializers import (
    PedidoCompraSerializer,
    PedidoVendaSerializer,
    PropostaSerializer,
)
from apps.produtos.models import FamiliaProduto, Produto


class ComercialPdfContentDispositionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cdisp', 'cdisp@test.com', 'secret123')
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.user)
        self.empresa = Empresa.objects.create(
            razao_social='Emitente CD',
            cnpj='12.345.678/0001-90',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cliente CD',
            cnpj='98.765.432/0001-10',
            uf='RJ',
        )
        self.forn = Fornecedor.objects.create(
            razao_social='Fornecedor CD',
            cnpj='11.222.333/0001-81',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FTCD',
            descricao_base='Fam CD',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao='Prod CD',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-CD',
            unidade='PC',
        )

    def _cdisp(self, resp) -> str:
        return resp['Content-Disposition']

    def test_proposta_pdf_content_disposition_inline_filename(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade': '2026-06-10',
                'status': 'Aberta',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '10',
                        'preco_por_unidade_negociada': '10',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        proposta = ser.save()
        url = reverse('proposta-pdf', kwargs={'pk': proposta.pk})
        resp = self.client_api.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        cd = self._cdisp(resp)
        self.assertIn('inline', cd)
        self.assertRegex(cd, r'filename="proposta-[^"]+\.pdf"')

    def test_pedido_venda_pdf_content_disposition_inline_filename(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-12',
                'status': 'ABERTO',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '10',
                        'preco_por_unidade_negociada': '10',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        url = reverse('pedidovenda-pdf', kwargs={'pk': pedido.pk})
        resp = self.client_api.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        cd = self._cdisp(resp)
        self.assertIn('inline', cd)
        self.assertRegex(cd, r'filename="pedido-venda-[^"]+\.pdf"')
        if pedido.numero:
            self.assertIn(pedido.numero.replace('/', '-'), cd)

    def test_pedido_compra_pdf_content_disposition_inline_filename(self):
        ser = PedidoCompraSerializer(
            data={
                'fornecedor_id': self.forn.id,
                'data': '2026-05-13',
                'status': 'Pendente',
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
        pedido = ser.save()
        url = reverse('pedidocompra-pdf', kwargs={'pk': pedido.pk})
        resp = self.client_api.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        cd = self._cdisp(resp)
        self.assertIn('inline', cd)
        self.assertRegex(cd, r'filename="pedido-compra-[^"]+\.pdf"')
        safe_num = re.sub(r'[/\\]+', '-', (pedido.numero or '').strip())
        if safe_num:
            self.assertIn(safe_num, cd)
