"""Dashboard home — o herói do card sempre chega no payload do card."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import PedidoCompra
from apps.fiscal.models import NFeSaida


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


MODULOS_HOME = ('comercial', 'fiscal', 'estoque', 'expedicao', 'compras', 'qualidade', 'financeiro')


class DashboardHomeHeroTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('home_hero_admin', 'admin@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.hoje = timezone.localdate()
        self.cliente = Cliente.objects.create(razao_social='Cliente Hero', cnpj=_cnpj(), uf='SC')
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn Hero', cnpj=_cnpj(), uf='SC')

    def _cards(self) -> dict:
        data = self.client.get('/api/dashboard/home/').json()
        return {m['modulo']: m for m in data['modulos']}

    def test_compras_card_inclui_o_hero_valor_aberto_compras(self):
        PedidoCompra.objects.create(
            numero='PC-HERO-A', fornecedor=self.fornecedor, data=self.hoje,
            status='ABERTO', valor_total=Decimal('80'),
        )
        PedidoCompra.objects.create(
            numero='PC-HERO-B', fornecedor=self.fornecedor, data=self.hoje,
            status='ABERTO', valor_total=Decimal('20'),
        )

        compras = self._cards()['compras']
        ids = [k['id'] for k in compras['kpis']]

        self.assertEqual(compras['hero_kpi_id'], 'valor_aberto_compras')
        self.assertIn(compras['hero_kpi_id'], ids)
        self.assertEqual(ids[0], 'valor_aberto_compras')
        self.assertEqual(compras['kpis'][0]['valor'], '100.00')
        self.assertEqual(len(compras['kpis']), 4)

    def test_hero_dinamico_fora_do_corte_tambem_chega_no_card(self):
        # Sem produção e com rejeitada em homologação, o herói de fiscal vira
        # nfe_rej_homolog — 5º KPI da lista, o primeiro que o corte antigo perdia.
        NFeSaida.objects.create(
            numero='NF-HERO-REJ',
            cliente=self.cliente,
            data=self.hoje,
            status='RASCUNHO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
            valor_total=1,
        )

        fiscal = self._cards()['fiscal']
        ids = [k['id'] for k in fiscal['kpis']]

        self.assertEqual(fiscal['hero_kpi_id'], 'nfe_rej_homolog')
        self.assertIn('nfe_rej_homolog', ids)
        self.assertEqual(ids[0], 'nfe_rej_homolog')

    def test_todo_card_da_home_tem_no_maximo_4_kpis_e_o_proprio_hero_primeiro(self):
        cards = self._cards()

        for modulo in MODULOS_HOME:
            with self.subTest(modulo=modulo):
                card = cards[modulo]
                ids = [k['id'] for k in card['kpis']]
                self.assertLessEqual(len(ids), 4)
                self.assertEqual(card['hero_kpi_id'], ids[0])
                self.assertEqual(len(ids), len(set(ids)), 'herói duplicado na lista do card')
