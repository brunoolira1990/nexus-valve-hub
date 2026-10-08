"""Comercial 2.6.2 — PDFs comerciais sem tags HTML cruas (<nobr>) visíveis."""

import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from pypdf import PdfReader

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda
from apps.comercial.pedido_compra_pdf import gerar_pedido_compra_pdf_bytes
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.proposta_pdf import gerar_proposta_pdf_bytes
from apps.comercial.serializers import (
    PedidoCompraSerializer,
    PedidoVendaSerializer,
    PropostaSerializer,
)
from apps.produtos.models import FamiliaProduto, Produto


def _pdf_text(pdf_bytes: bytes) -> str:
    text = ''
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        text += page.extract_text() or ''
    return text


def _assert_sem_nobr_cru(self, pdf_bytes: bytes, *, contexto: str):
    self.assertTrue(pdf_bytes.startswith(b'%PDF'), f'{contexto}: não é PDF')
    self.assertNotIn(b'<nobr>', pdf_bytes, f'{contexto}: bytes contêm <nobr>')
    self.assertNotIn(b'</nobr>', pdf_bytes, f'{contexto}: bytes contêm </nobr>')
    texto = _pdf_text(pdf_bytes)
    self.assertNotIn('<nobr>', texto, f'{contexto}: texto extraído contém <nobr>')
    self.assertNotIn('</nobr>', texto, f'{contexto}: texto extraído contém </nobr>')


class ComercialPdfNoMarkupTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social='Emitente Markup',
            cnpj='12.345.678/0001-90',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Markup',
            cnpj='98.765.432/0001-10',
            uf='RJ',
        )
        self.forn = Fornecedor.objects.create(
            razao_social='Fornecedor Markup',
            cnpj='11.222.333/0001-81',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FTMK',
            descricao_base='Fam Markup',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao='Produto markup',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-MK',
            unidade='PC',
            ncm='84818095',
        )

    def test_pedido_venda_resumo_faturamento_sem_nobr(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-14',
                'status': 'ABERTO',
                'condicao_pagamento_texto': '30',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '2',
                        'quantidade_negociada': '2',
                        'valor_unitario': '250',
                        'preco_por_unidade_negociada': '250',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        item = pedido.itens.first()
        criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.pk, 'quantidade': '1'}]},
        )
        fat = pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.RASCUNHO).first()
        confirmar_faturamento_pedido(pedido, fat.pk)

        pdf_bytes = gerar_pedido_venda_pdf_bytes(pedido)
        _assert_sem_nobr_cru(self, pdf_bytes, contexto='Pedido de Venda')
        texto = _pdf_text(pdf_bytes)
        self.assertIn('Faturada:', texto)
        self.assertIn('R$ 500,00', texto)
        self.assertIn('R$ 250,00', texto)

    def test_proposta_pdf_sem_nobr(self):
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
                        'valor_unitario': '100',
                        'preco_por_unidade_negociada': '100',
                        'unidade_negociada': 'PC',
                        'custo_utilizado': '40',
                        'lucro_resultante': '60',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        proposta = ser.save()
        pdf_bytes = gerar_proposta_pdf_bytes(proposta)
        _assert_sem_nobr_cru(self, pdf_bytes, contexto='Proposta')
        self.assertIn('R$ 100,00', _pdf_text(pdf_bytes))

    def test_pedido_compra_pdf_sem_nobr(self):
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
        pdf_bytes = gerar_pedido_compra_pdf_bytes(pedido)
        _assert_sem_nobr_cru(self, pdf_bytes, contexto='Pedido de Compra')
        self.assertIn('R$ 10,00', _pdf_text(pdf_bytes))
