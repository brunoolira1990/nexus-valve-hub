"""Testes ERP 4.0.8 — BI modular por permissões."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.comercial.models import PedidoCompra, PedidoVenda
from apps.fiscal.models import NFeSaida
from apps.produtos.models import Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class DashboardBI408Tests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('bi_admin', 'admin@test.com', 'x')
        self.comercial_user = get_user_model().objects.create_user('bi_com', 'com@test.com', 'x')
        self.sem_perm = get_user_model().objects.create_user('bi_none', 'none@test.com', 'x')
        ct = ContentType.objects.get(app_label='comercial', model='pedidovenda')
        perm = Permission.objects.get(content_type=ct, codename='view_pedidovenda')
        self.comercial_user.user_permissions.add(perm)

        self.client = APIClient()
        self.cliente = Cliente.objects.create(razao_social='Cliente BI', cnpj=_cnpj(), uf='SC')
        self.hoje = timezone.localdate()

    def test_home_retorna_apenas_modulos_permitidos(self):
        self.client.force_authenticate(self.comercial_user)
        data = self.client.get('/api/dashboard/home/').json()
        self.assertFalse(data['permissoes']['pode_ver_fiscal'])
        self.assertTrue(data['permissoes']['pode_ver_comercial'])
        modulos = {m['modulo'] for m in data['modulos']}
        self.assertIn('comercial', modulos)
        self.assertNotIn('fiscal', modulos)

    def test_usuario_sem_permissao_fiscal_recebe_403(self):
        self.client.force_authenticate(self.comercial_user)
        resp = self.client.get('/api/dashboard/fiscal/')
        self.assertEqual(resp.status_code, 403)

    def test_usuario_sem_permissao_financeiro_recebe_403(self):
        self.client.force_authenticate(self.comercial_user)
        resp = self.client.get('/api/dashboard/financeiro/')
        self.assertEqual(resp.status_code, 403)

    def test_admin_recebe_todos_modulos_home(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/home/').json()
        modulos = {m['modulo'] for m in data['modulos']}
        for m in ('comercial', 'fiscal', 'estoque', 'compras', 'qualidade', 'financeiro'):
            self.assertIn(m, modulos)

    def test_comercial_calcula_pedidos_abertos(self):
        PedidoVenda.objects.create(numero='PV-BI-1', cliente=self.cliente, data=self.hoje, status='ABERTO', valor_total=100)
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/comercial/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['pedidos_abertos']['valor'], 1)

    def test_comercial_rankings_limitados(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/comercial/').json()
        for r in data['rankings']:
            self.assertLessEqual(len(r['itens']), 5)

    def test_fiscal_nao_retorna_xml(self):
        NFeSaida.objects.create(numero='NF-BI', cliente=self.cliente, data=self.hoje, status='RASCUNHO', valor_total=1)
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/fiscal/').json()
        self.assertNotIn('xml', str(data).lower())

    def test_fiscal_calcula_por_status(self):
        NFeSaida.objects.create(
            numero='NF-REJ',
            cliente=self.cliente,
            data=self.hoje,
            status='RASCUNHO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
            valor_total=1,
        )
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/fiscal/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['nfe_rej_homolog']['valor'], 1)

    def test_estoque_produtos_sem_ncm(self):
        Produto.objects.create(codigo_completo='BI-NCM', descricao='X', material='Aço', ncm='')
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/estoque/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['produtos_sem_ncm']['valor'], 1)

    def test_compras_pedidos_por_status(self):
        from apps.cadastros.models import Fornecedor
        f = Fornecedor.objects.create(razao_social='Forn BI', cnpj=_cnpj(), uf='SC')
        PedidoCompra.objects.create(numero='PC-BI', fornecedor=f, data=self.hoje, status='ABERTO')
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/compras/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['pc_abertos']['valor'], 1)

    def test_financeiro_resumo_operacional(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/financeiro/').json()
        self.assertFalse(data.get('em_preparacao'))
        k = {x['id']: x for x in data['kpis']}
        self.assertIn('saldo_previsto', k)
        self.assertTrue(data.get('links'))

    def test_zeros_banco_vazio_modulo(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/comercial/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertEqual(k['pedidos_abertos']['valor'], 0)

    def test_filtro_periodo_personalizado(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/dashboard/comercial/', {
            'periodo': 'personalizado',
            'data_inicio': '2026-01-01',
            'data_fim': '2026-01-31',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['periodo']['data_inicio'], '2026-01-01')

    def test_resumo_compat_filtra_por_permissao(self):
        self.client.force_authenticate(self.comercial_user)
        data = self.client.get('/api/dashboard/resumo/').json()
        self.assertIn('comercial', data)
        self.assertEqual(data['fiscal']['nfe_saida_rascunhos'], 0)
        self.assertFalse(data['permissoes']['pode_ver_fiscal'])

    def test_usuario_sem_modulo_home_vazia(self):
        self.client.force_authenticate(self.sem_perm)
        data = self.client.get('/api/dashboard/home/').json()
        self.assertTrue(data['nenhum_modulo'])
        self.assertEqual(len(data['modulos']), 0)

    def test_alertas_drill_down_links(self):
        PedidoVenda.objects.create(numero='PV-AL', cliente=self.cliente, data=self.hoje, status='ABERTO', valor_total=50)
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/home/').json()
        links = [a['link'] for a in data['alertas'] if a.get('link')]
        self.assertTrue(any('/pedidos-venda' in l for l in links))
