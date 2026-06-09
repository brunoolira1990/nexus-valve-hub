"""Testes ERP 4.0.5 — paginação global."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import PedidoVenda
from apps.fiscal.models import NFeSaida
from apps.produtos.models import Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class PaginacaoGlobalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pag_user', 'pag@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(razao_social='Cliente Pag', cnpj=_cnpj(), uf='SC')
        hoje = timezone.localdate()
        for i in range(25):
            Empresa.objects.create(razao_social=f'Empresa Pag {i:02d}', cnpj=_cnpj(), uf='SC')
            Cliente.objects.create(razao_social=f'Cliente Pag {i:02d}', cnpj=_cnpj(), uf='SC')
            Produto.objects.create(codigo_completo=f'PAG-{i:03d}', descricao=f'Produto {i}', material='Aço')
        PedidoVenda.objects.create(
            numero='PV-PAG-001', cliente=self.cliente, data=hoje, status='ABERTO', valor_total=100,
        )
        NFeSaida.objects.create(
            numero='RASCUNHO-TEST', cliente=self.cliente, data=hoje, status='RASCUNHO', valor_total=50,
        )

    def _assert_paginated(self, url: str):
        resp = self.client.get(url, {'page': 1, 'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('count', data)
        self.assertIn('results', data)
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['page_size'], 20)
        self.assertLessEqual(len(data['results']), 20)
        return data

    def test_empresas_retorna_paginacao(self):
        data = self._assert_paginated('/api/empresas/')
        self.assertGreaterEqual(data['count'], 25)

    def test_clientes_retorna_paginacao(self):
        self._assert_paginated('/api/clientes/')

    def test_produtos_retorna_paginacao(self):
        self._assert_paginated('/api/produtos/')

    def test_pedidos_venda_retorna_paginacao(self):
        self._assert_paginated('/api/pedidos-venda/')

    def test_nfe_saida_retorna_paginacao(self):
        self._assert_paginated('/api/nf-saidas/')

    def test_busca_com_paginacao(self):
        resp = self.client.get('/api/empresas/', {'search': 'Empresa Pag 01', 'page': 1, 'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(any('Empresa Pag 01' in (r.get('razao_social') or '') for r in data['results']))

    def test_ordenacao_com_paginacao(self):
        resp = self.client.get('/api/clientes/', {'ordering': 'razao_social', 'page': 1, 'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        nomes = [r['razao_social'] for r in resp.json()['results']]
        self.assertEqual(nomes, sorted(nomes))

    def test_filtro_status_pedido(self):
        resp = self.client.get('/api/pedidos-venda/', {'status': 'ABERTO', 'page': 1})
        self.assertEqual(resp.status_code, 200)
        for row in resp.json()['results']:
            self.assertIn('ABERTO', (row.get('status') or '').upper())

    def test_page_size_acima_limite_cai_no_padrao(self):
        resp = self.client.get('/api/empresas/', {'page': 1, 'page_size': 500})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['page_size'], 20)

    def test_autocomplete_limit_sem_page(self):
        resp = self.client.get('/api/clientes/', {'limit': 5})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertLessEqual(len(data), 5)

    def test_listagem_nfe_nao_retorna_xml_grande(self):
        resp = self.client.get('/api/nf-saidas/', {'page': 1, 'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        for row in resp.json()['results']:
            self.assertNotIn('xml_autorizado', row)
            self.assertNotIn('xml_nfe', row)
