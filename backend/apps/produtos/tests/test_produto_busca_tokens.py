"""Busca de produtos por múltiplos termos parciais (autocomplete comercial)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.produtos.models import FamiliaProduto, Produto
from apps.produtos.produto_busca import (
    produto_atende_tokens,
    tokenizar_busca_produto,
    variantes_termo_busca,
)


def _familia(suf: str) -> FamiliaProduto:
    return FamiliaProduto.objects.create(
        codigo_figura=f'V{suf}',
        descricao_base='Válvulas',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )


class ProdutoBuscaTokensUnitTests(TestCase):
    def test_tokeniza_query_com_espacos(self):
        self.assertEqual(tokenizar_busca_produto('valvula inox 1/2'), ['valvula', 'inox', '1/2'])

    def test_variantes_polegada(self):
        vars_ = variantes_termo_busca('1/2')
        self.assertIn('1/2', vars_)
        self.assertTrue(any('"' in v or 'POL' in v.upper() for v in vars_))


class ProdutoBuscaTokensApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('busca_tok', 'busca_tok@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        suf = uuid.uuid4().hex[:6].upper()
        fam = _familia(suf)
        self.valvula = Produto.objects.create(
            familia=fam,
            descricao='VÁLVULA ESFERA TRIPARTIDA INOX 304 PP TP BSP 1/2"',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'VLX-{suf}',
            unidade='PC',
            ncm='84818099',
            material='INOX 304',
            polegada_principal='1/2"',
            conexao='BSP',
        )
        Produto.objects.create(
            familia=fam,
            descricao='UNIÃO AÇO INOX 316',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='00750D13',
            unidade='PC',
            ncm='84818200',
        )

    def _rows(self, resp):
        data = resp.json()
        return data if isinstance(data, list) else data.get('results', [])

    def test_busca_multiplos_termos_fora_de_ordem(self):
        for query in ('valvula inox 1/2', 'inox 1/2 valvula', '304 inox bsp'):
            resp = self.client.get('/api/produtos/', {'search': query, 'limit': 20})
            self.assertEqual(resp.status_code, 200, query)
            ids = [r['id'] for r in self._rows(resp)]
            self.assertIn(self.valvula.pk, ids, query)

    def test_busca_por_codigo_exato_continua(self):
        resp = self.client.get('/api/produtos/', {'search': self.valvula.codigo_completo, 'limit': 20})
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in self._rows(resp)]
        self.assertIn(self.valvula.pk, ids)

    def test_busca_sem_termo_lista_limitada(self):
        resp = self.client.get('/api/produtos/', {'limit': 5})
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(self._rows(resp)), 5)

    def test_produto_atende_tokens_helper(self):
        tokens = tokenizar_busca_produto('valvula inox 1/2')
        self.assertTrue(produto_atende_tokens(self.valvula, tokens))
        self.assertFalse(produto_atende_tokens(self.valvula, ['valvula', 'bronze']))
