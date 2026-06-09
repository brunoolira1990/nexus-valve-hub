"""Comercial 2.6.1 — NCM nos PDFs de Proposta, Pedido de Venda e Pedido de Compra."""

import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.comercial.comercial_pdf_shared import (
    NCM_NAO_INFORMADO,
    resolver_ncm_item_comercial,
)
from apps.comercial.models import ItemPedidoVenda, PedidoCompra
from apps.comercial.pedido_compra_pdf import gerar_pedido_compra_pdf_bytes
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.proposta_pdf import gerar_proposta_pdf_bytes
from apps.comercial.serializers import (
    PedidoCompraSerializer,
    PedidoVendaSerializer,
    PropostaSerializer,
)
from apps.fiscal.models import NFeSaida
from apps.produtos.models import FamiliaProduto, Produto
from pypdf import PdfReader


def _pdf_text(pdf_bytes: bytes) -> str:
    text = ''
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        text += page.extract_text() or ''
    return text


class ResolverNcmComercialTests(TestCase):
    def test_produto_ncm_direto(self):
        fam = FamiliaProduto.objects.create(
            codigo_figura='FTNCM',
            descricao_base='Fam NCM',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        prod = Produto.objects.create(
            familia=fam,
            descricao='Com NCM',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-NCM',
            unidade='PC',
            ncm='84818095',
        )
        self.assertEqual(
            resolver_ncm_item_comercial(produto=prod),
            '84818095',
        )

    def test_avulso_e_snapshot(self):
        self.assertEqual(
            resolver_ncm_item_comercial(ncm_avulso='84818099'),
            '84818099',
        )
        self.assertEqual(
            resolver_ncm_item_comercial(snapshot_fiscal={'ncm': '12345678'}),
            '12345678',
        )
        self.assertEqual(
            resolver_ncm_item_comercial(),
            NCM_NAO_INFORMADO,
        )


class ComercialPdfNcmFixture(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ncm_pdf', 'ncm@test.com', 'secret123')
        self.empresa = Empresa.objects.create(
            razao_social='Emitente NCM',
            cnpj='12.345.678/0001-90',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cliente NCM SA',
            cnpj='98.765.432/0001-10',
            uf='RJ',
        )
        self.forn = Fornecedor.objects.create(
            razao_social='Fornecedor NCM',
            cnpj='11.222.333/0001-81',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FTNCM2',
            descricao_base='Fam PDF NCM',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod_ncm = Produto.objects.create(
            familia=self.fam,
            descricao='Produto com NCM cadastrado',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-NCM-PDF',
            unidade='PC',
            ncm='84818095',
        )


class PropostaPdfNcmTests(ComercialPdfNcmFixture):
    def test_pdf_contem_ncm_produto(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade': '2026-06-10',
                'status': 'Aberta',
                'itens': [
                    {
                        'produto_id': self.prod_ncm.id,
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
        text = _pdf_text(gerar_proposta_pdf_bytes(proposta))
        self.assertIn('84818095', text)
        self.assertIn('NCM', text.upper())

    def test_pdf_contem_ncm_avulso(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_avulso_nome': 'Avulso NCM',
                'uf_destino_avulso': 'MG',
                'data': '2026-05-11',
                'validade': '2026-06-11',
                'status': 'Aberta',
                'itens': [
                    {
                        'descricao_avulsa': 'Linha avulsa NCM',
                        'ncm_avulso': '84818099',
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '5',
                        'preco_por_unidade_negociada': '5',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        proposta = ser.save()
        text = _pdf_text(gerar_proposta_pdf_bytes(proposta))
        self.assertIn('84818099', text)

    def test_pdf_avulso_sem_ncm_exibe_nao_informado(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_avulso_nome': 'Avulso sem NCM',
                'uf_destino_avulso': 'SP',
                'data': '2026-05-12',
                'validade': '2026-06-12',
                'status': 'Aberta',
                'itens': [
                    {
                        'descricao_avulsa': 'Sem NCM manual',
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '1',
                        'preco_por_unidade_negociada': '1',
                        'unidade_negociada': 'UN',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        proposta = ser.save()
        text = _pdf_text(gerar_proposta_pdf_bytes(proposta))
        self.assertIn('NCM', text.upper())
        self.assertIn('INFORMADO', text.upper())


class PedidoVendaPdfNcmTests(ComercialPdfNcmFixture):
    def test_pdf_contem_ncm_produto(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-12',
                'status': 'ABERTO',
                'itens': [
                    {
                        'produto_id': self.prod_ncm.id,
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '20',
                        'preco_por_unidade_negociada': '20',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        text = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertIn('84818095', text)

    def test_pdf_contem_ncm_snapshot_fiscal(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-13',
                'status': 'ABERTO',
                'itens': [
                    {
                        'produto_id': self.prod_ncm.id,
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '15',
                        'preco_por_unidade_negociada': '15',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        item = pedido.itens.first()
        self.prod_ncm.ncm = ''
        self.prod_ncm.save(update_fields=['ncm'])
        ItemPedidoVenda.objects.filter(pk=item.pk).update(
            snapshot_fiscal={'ncm': '73079900'},
        )
        text = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertIn('73079900', text)

    def test_get_pdf_application_pdf_sem_efeitos_fiscais(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-14',
                'status': 'ABERTO',
                'itens': [
                    {
                        'produto_id': self.prod_ncm.id,
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
        nfe_antes = NFeSaida.objects.count()
        c = APIClient()
        c.force_authenticate(user=self.user)
        resp = c.get(f'/api/pedidos-venda/{pedido.pk}/pdf/', HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(NFeSaida.objects.count(), nfe_antes)


class PedidoCompraPdfNcmTests(ComercialPdfNcmFixture):
    def test_pdf_contem_ncm_produto(self):
        ser = PedidoCompraSerializer(
            data={
                'fornecedor_id': self.forn.id,
                'data': '2026-05-13',
                'status': 'Pendente',
                'itens': [
                    {
                        'produto_id': self.prod_ncm.id,
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
        pedido: PedidoCompra = ser.save()
        text = _pdf_text(gerar_pedido_compra_pdf_bytes(pedido))
        self.assertIn('84818095', text)
        self.assertIn('NCM', text.upper())
