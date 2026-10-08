"""Busca paginada de clientes (autocomplete comercial)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class BuscaClienteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('busca_cli', 'busca_cli@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        Cliente.objects.create(razao_social='Revisão PDF CQ Ltda', cnpj=_cnpj(), uf='SP')
        Cliente.objects.create(razao_social='Outro Cliente XYZ', cnpj=_cnpj(), uf='RJ')

    def test_busca_por_razao_social(self):
        resp = self.client.get('/api/clientes/', {'search': 'Revisão PDF', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        self.assertTrue(any('Revisão PDF' in (r.get('razao_social') or '') for r in rows))

    def test_busca_vazia_respeita_limite(self):
        resp = self.client.get('/api/clientes/', {'limit': 1})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        self.assertLessEqual(len(rows), 1)

    def test_busca_por_nome_fantasia(self):
        Cliente.objects.filter(razao_social='Outro Cliente XYZ').update(nome_fantasia='Fantasia XYZ Comercial')
        resp = self.client.get('/api/clientes/', {'search': 'Fantasia XYZ', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(any('Fantasia XYZ' in (r.get('nome_fantasia') or '') for r in rows))

    def test_busca_por_cnpj_com_mascara(self):
        cli = Cliente.objects.create(razao_social='Cliente CNPJ Mascara', cnpj='59443075000120', uf='SP')
        resp = self.client.get('/api/clientes/', {'search': '59.443.075/0001-20', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(any(r.get('id') == cli.pk for r in rows))

    def test_busca_por_cnpj_sem_mascara(self):
        cli = Cliente.objects.create(razao_social='Cliente CNPJ Digitos', cnpj='59443075000120', uf='RJ')
        resp = self.client.get('/api/clientes/', {'search': '59443075000120', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json() if isinstance(resp.json(), list) else resp.json().get('results', [])
        self.assertTrue(any(r.get('id') == cli.pk for r in rows))
