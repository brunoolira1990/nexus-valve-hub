"""Testes ERP 4.0.8.1 — locale pt-BR do período BI."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from nexus_erp.dashboard_filters import parse_dashboard_filters


class DashboardBI4081LocaleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('bi_locale', 'locale@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_mes_atual_label_pt_br(self):
        hoje = timezone.localdate()
        f = parse_dashboard_filters({'periodo': 'mes_atual'})
        self.assertIn(str(hoje.year), f.label)
        self.assertNotIn('May', f.label)
        self.assertNotIn('MAY', f.label)
        meses_en = ('January', 'February', 'March', 'April', 'May', 'June')
        for m in meses_en:
            self.assertNotIn(m, f.label)

    def test_ultimos_30_dias_label(self):
        f = parse_dashboard_filters({'periodo': 'ultimos_30_dias'})
        self.assertEqual(f.label, 'Últimos 30 dias')

    def test_periodo_personalizado_formato_br(self):
        f = parse_dashboard_filters({
            'periodo': 'personalizado',
            'data_inicio': '2026-05-01',
            'data_fim': '2026-05-24',
        })
        self.assertEqual(f.label, '01/05/2026 a 24/05/2026')

    def test_home_periodo_pt_br_api(self):
        data = self.client.get('/api/dashboard/home/').json()
        label = data['periodo']['label']
        self.assertNotIn('May', label)
        self.assertNotIn('MAY', label)

    def test_financeiro_resumo_operacional(self):
        data = self.client.get('/api/dashboard/financeiro/').json()
        self.assertFalse(data.get('em_preparacao'))
        k = {x['id']: x for x in data['kpis']}
        self.assertIn('saldo_previsto', k)
        self.assertIn('cr_aberto', k)

    def test_permissoes_endpoint(self):
        data = self.client.get('/api/dashboard/permissoes/').json()
        self.assertTrue(data['pode_ver_comercial'])
