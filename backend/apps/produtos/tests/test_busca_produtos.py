"""Busca paginada de produtos (autocomplete comercial)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.produtos.models import FamiliaProduto, Produto


class BuscaProdutoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('busca_prod', 'busca_prod@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        suf = uuid.uuid4().hex[:6].upper()
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'B{suf}',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        Produto.objects.create(
            familia=fam,
            descricao='UNIÃO AÇO INOX 316',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='00750D13',
            unidade='PC',
            ncm='84818200',
        )

    def test_busca_por_codigo(self):
        resp = self.client.get('/api/produtos/', {'search': '00750D', 'limit': 20})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        self.assertTrue(any('00750D' in (r.get('codigo_completo') or '') for r in rows))

    def test_busca_sem_resultado(self):
        resp = self.client.get('/api/produtos/', {'search': 'ZZZNOMATCH999', 'limit': 10})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        self.assertEqual(len(rows), 0)
