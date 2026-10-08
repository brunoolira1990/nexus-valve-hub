"""ERP 4.0.14.9.3 — cabeçalho operacional: busca global e contexto."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Colaborador, Empresa, Fornecedor
from apps.comercial.models import PedidoVenda, Proposta
from apps.core.busca_global import executar_busca_global
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import NFeSaida
from apps.produtos.models import Produto

User = get_user_model()


class BuscaGlobal401493Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('busca401493', 'busca401493@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.empresa = Empresa.objects.create(
            razao_social='NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
            nome_fantasia='NEXUS VÁLVULAS',
            cnpj='12345678000199',
        )
        self.cliente = Cliente.objects.create(
            razao_social='PETROBRAS TRANSPORTE S.A.',
            cnpj='33000167000101',
        )
        self.fornecedor = Fornecedor.objects.create(
            razao_social='COMERCIAL CONEFER LTDA',
            cnpj='98765432000188',
        )
        self.produto = Produto.objects.create(descricao='VÁLVULA ESFERA 1/2', codigo_completo='VE-001')
        self.cr = TituloFinanceiro.objects.create(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            numero='CR-2026-000003',
            cliente=self.cliente,
            data_emissao='2026-01-15',
            data_vencimento='2026-02-15',
            valor_original=Decimal('12500'),
            valor_aberto=Decimal('12500'),
            status=TituloFinanceiro.Status.EM_ABERTO,
        )
        self.nfe = NFeSaida.objects.create(
            numero='000000003',
            cliente=self.cliente,
            data='2026-01-10',
            valor_total=Decimal('1000'),
            status='Autorizada',
        )

    def test_query_curta_vazia(self):
        res = executar_busca_global('a')
        self.assertEqual(res['resultados'], [])
        self.assertIn('2 caracteres', res.get('mensagem', '').lower())

    def test_busca_cliente(self):
        res = executar_busca_global('PETROBRAS')
        tipos = [r['tipo'] for r in res['resultados']]
        self.assertIn('cliente', tipos)
        self.assertNotIn('password', str(res).lower())

    def test_busca_fornecedor(self):
        res = executar_busca_global('CONEFER')
        self.assertTrue(any(r['tipo'] == 'fornecedor' for r in res['resultados']))

    def test_busca_produto(self):
        res = executar_busca_global('VÁLVULA ESFERA')
        self.assertTrue(any(r['tipo'] == 'produto' for r in res['resultados']))

    def test_busca_cr(self):
        res = executar_busca_global('CR-2026-000003')
        self.assertTrue(any(r['tipo'] == 'conta_receber' for r in res['resultados']))

    def test_busca_nfe_saida(self):
        res = executar_busca_global('000000003')
        self.assertTrue(any(r['tipo'] == 'nfe_saida' for r in res['resultados']))

    def test_endpoint_exige_auth(self):
        anon = APIClient()
        r = anon.get('/api/busca-global/', {'q': 'petro'})
        self.assertEqual(r.status_code, 401)

    def test_contexto_empresa(self):
        r = self.client.get('/api/app/contexto/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data['empresa']['nome_exibicao'],
            'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
        )
        self.assertIn('usuario', r.data)

    def test_minha_conta(self):
        r = self.client.get('/api/minha-conta/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['usuario']['username'], 'busca401493')

    def test_api_busca_global(self):
        r = self.client.get('/api/busca-global/', {'q': 'PETRO'})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.data['resultados']), 0)
        for item in r.data['resultados']:
            self.assertIn('url', item)
            self.assertIn('titulo', item)
            self.assertNotIn('content_type', item)
