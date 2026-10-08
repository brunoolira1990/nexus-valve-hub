"""Primitivas de baixa/consumo de EstoqueBarra (peça/chapa em KG ou barra em M)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.fiscal.aplicacao_estoque_conferencia import aplicar_estoque_fisico_conferencia
from apps.fiscal.baixa_estoque_barra import baixar_peca_estoque, reverter_baixa_peca_estoque
from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia
from apps.fiscal.models import EstoqueBarra
from apps.fiscal.tests.test_conferencia_equivalencia_entrada import (
    _criar_composicao_quatro_chapas,
    _setup_chapa_conferencia,
)


class BaixaEstoqueBarraTests(TestCase):
    def setUp(self):
        ctx = _setup_chapa_conferencia('BX1', qty='486.300')
        linha = ctx['linha']
        _criar_composicao_quatro_chapas(linha)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.pecas = list(
            EstoqueBarra.objects.filter(item_conferencia=linha).order_by('equivalencia_entrada__ordem'),
        )
        self.assertEqual(len(self.pecas), 4)

    def test_baixa_integral_marca_consumida(self):
        peca = self.pecas[0]
        peso = peca.saldo
        barra = baixar_peca_estoque(peca.id, peso)
        self.assertEqual(barra.status, EstoqueBarra.Status.CONSUMIDA)
        self.assertEqual(barra.saldo, Decimal('0'))

    def test_baixa_parcial_marca_parcial(self):
        peca = self.pecas[1]
        original = peca.quantidade_original
        parcial = Decimal('50.000')
        barra = baixar_peca_estoque(peca.id, parcial)
        self.assertEqual(barra.status, EstoqueBarra.Status.PARCIAL)
        self.assertEqual(barra.saldo, original - parcial)

    def test_baixa_maior_que_saldo_bloqueia(self):
        peca = self.pecas[2]
        with self.assertRaises(ValueError):
            baixar_peca_estoque(peca.id, peca.saldo + Decimal('1'))

    def test_reverter_baixa_parcial_volta_disponivel(self):
        peca = self.pecas[3]
        original = peca.quantidade_original
        parcial = Decimal('22.450')
        baixar_peca_estoque(peca.id, parcial)
        barra = reverter_baixa_peca_estoque(peca.id, parcial)
        self.assertEqual(barra.status, EstoqueBarra.Status.DISPONIVEL)
        self.assertEqual(barra.saldo, original)
