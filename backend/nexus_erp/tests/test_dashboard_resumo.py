"""Testes ERP 4.0.6 — dashboard operacional real."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.comercial.models import PedidoVenda
from apps.fiscal.models import NFeSaida
from apps.produtos.models import Produto


class DashboardResumoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('dash_user', 'dash@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(razao_social='Cliente Dash', cnpj='12.345.678/0001-99', uf='SC')
        self.hoje = timezone.localdate()

    def _get(self):
        resp = self.client.get('/api/dashboard/resumo/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_dashboard_nao_retorna_dados_hardcoded(self):
        data = self._get()
        self.assertNotIn('125.000', str(data))
        self.assertNotIn('Petrobrás', str(data))

    def test_dashboard_zeros_banco_vazio(self):
        data = self._get()
        self.assertEqual(data['comercial']['pedidos_abertos'], 0)
        self.assertEqual(data['estoque']['produtos_cadastrados'], 0)
        self.assertEqual(data['financeiro']['contas_receber_aberto'], '0.00')

    def test_dashboard_calcula_pedidos_abertos(self):
        PedidoVenda.objects.create(numero='PV-1', cliente=self.cliente, data=self.hoje, status='ABERTO', valor_total=100)
        PedidoVenda.objects.create(numero='PV-2', cliente=self.cliente, data=self.hoje, status='ABERTO', valor_total=200)
        data = self._get()
        self.assertEqual(data['comercial']['pedidos_abertos'], 2)

    def test_dashboard_calcula_pedidos_parciais(self):
        PedidoVenda.objects.create(
            numero='PV-P', cliente=self.cliente, data=self.hoje, status='PARCIALMENTE_FATURADO', valor_total=100,
        )
        data = self._get()
        self.assertGreaterEqual(data['comercial']['pedidos_parcialmente_faturados'], 1)

    def test_dashboard_calcula_nfe_por_status(self):
        NFeSaida.objects.create(
            numero='R1', cliente=self.cliente, data=self.hoje, status='RASCUNHO', valor_total=1,
        )
        NFeSaida.objects.create(
            numero='R2',
            cliente=self.cliente,
            data=self.hoje,
            status='RASCUNHO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
            valor_total=1,
        )
        data = self._get()
        self.assertGreaterEqual(data['fiscal']['nfe_saida_rascunhos'], 1)
        self.assertGreaterEqual(data['fiscal']['nfe_saida_rejeitadas_homologacao'], 1)

    def test_dashboard_produtos_sem_ncm(self):
        Produto.objects.create(codigo_completo='SEM-NCM', descricao='X', material='Aço', ncm='')
        data = self._get()
        self.assertGreaterEqual(data['estoque']['produtos_sem_ncm'], 1)

    def test_dashboard_limita_ultimas_listas(self):
        for i in range(12):
            PedidoVenda.objects.create(
                numero=f'PV-{i}', cliente=self.cliente, data=self.hoje, status='ABERTO', valor_total=10,
            )
        data = self._get()
        self.assertLessEqual(len(data['comercial']['ultimos_pedidos']), 5)

    def test_dashboard_financeiro_operacional(self):
        data = self._get()
        self.assertEqual(data['financeiro']['modulo'], 'operacional')
        self.assertEqual(data['financeiro']['contas_pagar_aberto'], '0.00')
        self.assertEqual(data['financeiro']['saldo_previsto'], '0.00')
