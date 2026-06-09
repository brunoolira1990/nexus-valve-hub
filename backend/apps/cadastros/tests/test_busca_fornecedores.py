"""Busca paginada de fornecedores (autocomplete financeiro/comercial)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor


def _cnpj(seed: int) -> str:
    h = seed % 10_000_000_000_000
    return f'{h:014d}'


class BuscaFornecedorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('busca_forn', 'busca_forn@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.forn = Fornecedor.objects.create(
            razao_social='WINNER EXPRESS TRANSPORTES LTDA',
            nome_fantasia='Winner Express',
            cnpj='32241095000121',
            uf='SP',
        )
        Fornecedor.objects.create(
            razao_social='Outro Fornecedor ABC',
            cnpj=_cnpj(int(uuid.uuid4().hex[:8], 16)),
            uf='RJ',
        )

    def test_busca_por_razao_social(self):
        resp = self.client.get('/api/fornecedores/', {'search': 'WINNER EXPRESS', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(any('WINNER EXPRESS' in (r.get('razao_social') or '') for r in rows))

    def test_busca_por_cnpj_com_mascara(self):
        resp = self.client.get('/api/fornecedores/', {'search': '32.241.095/0001-21', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(any(r.get('id') == self.forn.pk for r in rows))

    def test_busca_por_cnpj_sem_mascara(self):
        resp = self.client.get('/api/fornecedores/', {'search': '32241095000121', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(any(r.get('id') == self.forn.pk for r in rows))

    def test_resposta_nao_expoe_campos_tecnicos_extras(self):
        resp = self.client.get('/api/fornecedores/', {'search': 'WINNER', 'limit': 1})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(rows)
        row = rows[0]
        self.assertIn('razao_social', row)
        self.assertIn('cnpj', row)
        self.assertNotIn('password', row)
