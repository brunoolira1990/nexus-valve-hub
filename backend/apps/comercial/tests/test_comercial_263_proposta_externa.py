"""Comercial 2.6.3 — PDF externo da proposta, prazo de entrega e conversão."""

import io
from decimal import Decimal

from django.test import TestCase
from pypdf import PdfReader

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.converter_proposta_pedido import converter_proposta_em_pedido_venda
from apps.comercial.models import PedidoVenda, Proposta
from apps.comercial.pedido_compra_pdf import gerar_pedido_compra_pdf_bytes
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.proposta_pdf import gerar_proposta_pdf_bytes
from apps.comercial.serializers import PedidoCompraSerializer, PropostaSerializer
from apps.comercial.tests.test_converter_proposta_pedido import _item, _produto, _proposta_aprovada
from apps.cadastros.models import Fornecedor
from apps.produtos.models import FamiliaProduto, Produto


def _pdf_text(pdf_bytes: bytes) -> str:
    text = ''
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        text += page.extract_text() or ''
    return text


class PropostaPrazoEntregaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social='Emit 263',
            cnpj='12.345.678/0001-90',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cli 263',
            cnpj='98.765.432/0001-10',
            uf='RJ',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FT263',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao='Prod 263',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-263',
            unidade='PC',
            ncm='84818095',
        )

    def test_proposta_aceita_prazo_entrega_texto(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade': '2026-06-10',
                'status': 'Aberta',
                'prazo_entrega_texto': '30 dias após aprovação',
                'condicao_pagamento_texto': '30',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '100',
                        'preco_por_unidade_negociada': '100',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        p = ser.save()
        self.assertEqual(p.prazo_entrega_texto, '30 dias após aprovação')

    def test_conversao_copia_prazo_entrega_texto(self):
        p = _proposta_aprovada()
        p.prazo_entrega_texto = '15 dias úteis após pedido'
        p.save(update_fields=['prazo_entrega_texto'])
        prod = _produto()
        _item(p, prod)
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.prazo_entrega_texto, '15 dias úteis após pedido')
        self.assertIsNone(pedido.prazo_entrega)


class PropostaPdfExternoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social='Emit PDF Ext',
            cnpj='12.345.678/0001-91',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cli PDF Ext',
            cnpj='98.765.432/0001-11',
            uf='RJ',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FTEXT',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao='Válvula PDF',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-EXT',
            unidade='PC',
            ncm='84818095',
        )

    def _proposta_com_cenario(self) -> Proposta:
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade': '2026-06-10',
                'status': 'Aprovada',
                'usar_cenario_fiscal_saida': True,
                'prazo_entrega_texto': '30 dias após aprovação do pedido',
                'condicao_pagamento_texto': '30',
                'homologacao_fiscal_observacao': 'Obs interna fiscal',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '2',
                        'quantidade_negociada': '2',
                        'valor_unitario': '250',
                        'preco_por_unidade_negociada': '250',
                        'unidade_negociada': 'PC',
                        'custo_utilizado': '100',
                        'lucro_resultante': '400',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        return ser.save()

    def test_pdf_externo_sem_dados_internos(self):
        proposta = self._proposta_com_cenario()
        pdf_bytes = gerar_proposta_pdf_bytes(proposta)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        text = _pdf_text(pdf_bytes).upper()
        self.assertIn('30 DIAS', text)
        self.assertIn('84818095', text)
        self.assertIn('R$', text)
        for forbidden in (
            'FONTE FISCAL',
            'CENÁRIO FISCAL',
            'CENARIO FISCAL',
            'RENTABILIDADE COMERCIAL',
            'CUSTO ESTIMADO',
            'LUCRO ESTIMADO',
            'MARGEM ESTIMADA',
            'OBS INTERNA',
        ):
            self.assertNotIn(forbidden, text, f'PDF não deve conter {forbidden}')

    def test_pdf_pedido_venda_com_prazo_texto(self):
        p = _proposta_aprovada()
        p.prazo_entrega_texto = 'Entrega em 20 dias'
        p.save(update_fields=['prazo_entrega_texto'])
        prod = _produto()
        _item(p, prod, icms=Decimal('18'))
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        pdf_bytes = gerar_pedido_venda_pdf_bytes(pedido)
        text = _pdf_text(pdf_bytes)
        self.assertIn('Entrega em 20 dias', text)
        self.assertNotIn('<nobr>', text)

    def test_pdf_pedido_compra_inalterado(self):
        forn = Fornecedor.objects.create(razao_social='Forn PC', cnpj='11.222.333/0001-81')
        ser = PedidoCompraSerializer(
            data={
                'fornecedor_id': forn.id,
                'data': '2026-05-13',
                'status': 'Pendente',
                'prazo_entrega_texto': '15 dias',
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
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertIn('15 DIAS', _pdf_text(pdf_bytes).upper())
