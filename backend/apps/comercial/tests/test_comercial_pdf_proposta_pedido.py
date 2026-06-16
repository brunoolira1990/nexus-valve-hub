"""PDF Proposta e Pedido de Venda — rotas, conteúdo e efeitos colaterais."""

import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemProposta, PedidoVenda, Proposta
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.proposta_pdf import gerar_proposta_pdf_bytes
from apps.comercial.serializers import PedidoVendaSerializer, PropostaSerializer
from apps.fiscal.models import NFeSaida
from apps.produtos.models import FamiliaProduto, Produto
from pypdf import PdfReader


class PropostaPdfRouteTests(TestCase):
    def test_url_resolve(self):
        m = resolve('/api/propostas/12/pdf/')
        self.assertEqual(m.url_name, 'proposta-pdf')
        self.assertEqual(str(m.kwargs.get('pk')), '12')

    def test_reverse(self):
        self.assertEqual(reverse('proposta-pdf', kwargs={'pk': 1}), '/api/propostas/1/pdf/')


class PedidoVendaPdfRouteTests(TestCase):
    def test_url_resolve(self):
        m = resolve('/api/pedidos-venda/7/pdf/')
        self.assertEqual(m.url_name, 'pedidovenda-pdf')
        self.assertEqual(str(m.kwargs.get('pk')), '7')

    def test_reverse(self):
        self.assertEqual(reverse('pedidovenda-pdf', kwargs={'pk': 1}), '/api/pedidos-venda/1/pdf/')


class ComercialPdfBaseFixture(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pdf_com', 'pdf_com@test.com', 'secret123')
        self.empresa = Empresa.objects.create(
            razao_social='Nexus Emitente PDF',
            cnpj='12.345.678/0001-90',
            uf='SP',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cliente PDF SA',
            nome_fantasia='Cliente PDF',
            cnpj='98.765.432/0001-10',
            uf='RJ',
        )
        self.fam = FamiliaProduto.objects.create(
            codigo_figura='FTPDF2',
            descricao_base='Fam PDF',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=self.fam,
            descricao='Produto PDF Teste',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PR-PDF-PROP',
            unidade='PC',
        )


class PropostaPdfResponseTests(ComercialPdfBaseFixture):
    def setUp(self):
        super().setUp()
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade': '2026-06-10',
                'status': 'Aberta',
                'vendedor': 'Vendedor Legado',
                'condicao_pagamento_texto': '30,60',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '2',
                        'quantidade_negociada': '2',
                        'valor_unitario': '100',
                        'preco_por_unidade_negociada': '100',
                        'unidade_negociada': 'PC',
                        'desconto': '10',
                        'custo_utilizado': '50',
                        'lucro_resultante': '140',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.proposta: Proposta = ser.save()
        self.status_antes = self.proposta.status

    def test_get_pdf_200_application_pdf(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('proposta-pdf', kwargs={'pk': self.proposta.pk})
        resp = c.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('proposta-', resp['Content-Disposition'])
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_pdf_bytes_contem_numero_cliente(self):
        pdf_bytes = gerar_proposta_pdf_bytes(self.proposta)
        text = ''
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            text += page.extract_text() or ''
        self.assertIn(self.proposta.numero, text)
        self.assertIn('Cliente PDF', text)
        self.assertIn('PR-PDF-PROP', text)

    def test_pdf_nao_altera_status_proposta(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('proposta-pdf', kwargs={'pk': self.proposta.pk})
        c.get(url, HTTP_HOST='localhost')
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.status, self.status_antes)


class PropostaPdfItemAvulsoTests(ComercialPdfBaseFixture):
    def test_proposta_item_avulso_pdf(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_avulso_nome': 'Cliente Avulso PDF',
                'uf_destino_avulso': 'MG',
                'data': '2026-05-11',
                'validade': '2026-06-11',
                'status': 'Aberta',
                'condicao_pagamento_texto': '30',
                'itens': [
                    {
                        'descricao_avulsa': 'Item avulso especial',
                        'ncm_avulso': '84818099',
                        'quantidade': '1',
                        'quantidade_negociada': '1',
                        'valor_unitario': '50',
                        'preco_por_unidade_negociada': '50',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        proposta = ser.save()
        pdf_bytes = gerar_proposta_pdf_bytes(proposta)
        text = ''
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            text += page.extract_text() or ''
        self.assertIn('ITEM AVULSO ESPECIAL', text.upper())
        self.assertIn('CLIENTE AVULSO PDF', text.upper())
        self.assertNotIn('CLIENTE (AVULSO)', text.upper())
        self.assertIn('84818099', text)


class PropostaPdfCamposComerciaisTests(ComercialPdfBaseFixture):
    def test_pdf_exibe_campos_comerciais_quando_preenchidos(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade_dias': 7,
                'status': 'Aberta',
                'condicao_pagamento_texto': '30',
                'referencia_cliente': 'REQ-2026-001',
                'frete_texto': 'FOB – POSTO / SP',
                'observacoes_proposta': 'Observação comercial\nlinha 2',
                'mensagem_comercial': 'A regra é não perder pedidos.',
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
        proposta = ser.save()
        pdf_bytes = gerar_proposta_pdf_bytes(proposta)
        text = ''
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            text += page.extract_text() or ''
        self.assertIn('REQ-2026-001', text)
        self.assertIn('FOB', text.upper())
        self.assertIn('OBSERVA', text.upper())
        self.assertIn('PERDER PEDIDOS', text.upper())
        self.assertIn('PC', text)
        self.assertIn('30 DDL', text)
        self.assertNotIn('STATUS:', text.upper())
        upper = text.upper()
        idx_itens = upper.find('ITENS')
        idx_obs = upper.find('OBSERV')
        idx_msg = upper.find('PERDER PEDIDOS')
        self.assertGreater(idx_itens, -1)
        self.assertGreater(idx_obs, idx_itens)
        self.assertGreater(idx_msg, idx_obs)

    def test_pdf_condicao_pagamento_texto_livre(self):
        ser = PropostaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-10',
                'validade_dias': 10,
                'status': 'Pendente',
                'condicao_pagamento_texto': 'À vista',
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
        proposta = ser.save()
        text = ''
        for page in PdfReader(io.BytesIO(gerar_proposta_pdf_bytes(proposta))).pages:
            text += page.extract_text() or ''
        self.assertIn('VISTA', text.upper())
        self.assertNotIn('PENDENTE', text.upper())


class PedidoVendaListIdTests(ComercialPdfBaseFixture):
    def test_listagem_inclui_id_para_pdf(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-12',
                'status': 'ABERTO',
                'condicao_pagamento_texto': '30',
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
        c = APIClient()
        c.force_authenticate(user=self.user)
        resp = c.get('/api/pedidos-venda/', HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        row = next(r for r in rows if r.get('numero') == pedido.numero)
        self.assertEqual(row['id'], pedido.pk)


class PedidoVendaPdfResponseTests(ComercialPdfBaseFixture):
    def setUp(self):
        super().setUp()
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-12',
                'status': 'ABERTO',
                'vendedor': 'Vend PDF',
                'condicao_pagamento_texto': '30',
                'observacoes_comerciais': 'Obs comercial PDF',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '3',
                        'quantidade_negociada': '3',
                        'valor_unitario': '20',
                        'preco_por_unidade_negociada': '20',
                        'unidade_negociada': 'PC',
                        'desconto': '0',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.pedido: PedidoVenda = ser.save()
        self.status_antes = self.pedido.status

    def test_get_pdf_200_application_pdf(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('pedidovenda-pdf', kwargs={'pk': self.pedido.pk})
        resp = c.get(url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('pedido-venda-', resp['Content-Disposition'])
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_pdf_bytes_contem_numero_cliente_itens(self):
        pdf_bytes = gerar_pedido_venda_pdf_bytes(self.pedido)
        text = ''
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            text += page.extract_text() or ''
        self.assertIn(self.pedido.numero, text)
        self.assertIn('Cliente PDF', text)
        self.assertIn('Resumo de faturamento', text)

    def test_pdf_nao_altera_status_pedido(self):
        c = APIClient()
        c.force_authenticate(user=self.user)
        url = reverse('pedidovenda-pdf', kwargs={'pk': self.pedido.pk})
        c.get(url, HTTP_HOST='localhost')
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, self.status_antes)

    def test_pdf_nao_cria_nfe_nem_faturamento_extra(self):
        nfe_antes = NFeSaida.objects.count()
        fat_antes = FaturamentoPedidoVenda.objects.filter(pedido=self.pedido).count()
        gerar_pedido_venda_pdf_bytes(self.pedido)
        self.assertEqual(NFeSaida.objects.count(), nfe_antes)
        self.assertEqual(FaturamentoPedidoVenda.objects.filter(pedido=self.pedido).count(), fat_antes)


class PedidoVendaPdfFaturamentoTests(ComercialPdfBaseFixture):
    def test_pedido_com_faturamento_nfe_nao_exibe_fiscal_no_pdf_comercial(self):
        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-13',
                'status': 'ABERTO',
                'condicao_pagamento_texto': '30',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '2',
                        'quantidade_negociada': '2',
                        'valor_unitario': '50',
                        'preco_por_unidade_negociada': '50',
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
        self.assertIsNotNone(fat)
        confirmar_faturamento_pedido(pedido, fat.pk)
        fat.refresh_from_db()
        fat.status = FaturamentoPedidoVenda.Status.GERADO_NFE
        nfe = NFeSaida.objects.create(
            numero='NF-PDF-001',
            status='rascunho',
            cliente=self.cliente,
            data='2026-05-13',
        )
        fat.nfe_saida = nfe
        fat.save(update_fields=['status', 'nfe_saida'])

        pdf_bytes = gerar_pedido_venda_pdf_bytes(pedido)
        text = ''
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            text += page.extract_text() or ''
        self.assertIn('Resumo de faturamento', text)
        self.assertNotIn('NF-PDF-001', text)
        self.assertNotIn('NF-e vinculada', text)
