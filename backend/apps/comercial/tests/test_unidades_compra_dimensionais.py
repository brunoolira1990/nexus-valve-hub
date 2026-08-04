"""Unidades negociáveis de compra em produtos dimensionais (barra/metro)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.comercial.conversao_item_comercial import _allowed_unidades_negociacao
from apps.produtos.models import FamiliaProduto, Produto


class UnidadesCompraDimensionaisTests(TestCase):
    def setUp(self):
        self.familia = FamiliaProduto.objects.create(
            codigo_figura='TB',
            descricao_base='Tubos',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
            usa_conversao_dimensional=True,
            tipo_composicao_fisica=FamiliaProduto.TipoComposicaoFisica.BARRA_M,
            comprimento_padrao_barra_m=Decimal('6'),
            peso_por_metro_kg=Decimal('1.5'),
            unidade_estoque_padrao='BR',
            unidade_compra_padrao='BR',
        )
        self.produto = Produto.objects.create(
            familia=self.familia,
            descricao='TUBO TESTE',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='TB-TEST',
            unidade='BR',
            usa_conversao_dimensional=True,
            tipo_composicao_fisica=FamiliaProduto.TipoComposicaoFisica.BARRA_M,
            comprimento_padrao_barra_m=Decimal('6'),
            peso_por_metro_kg=Decimal('1.5'),
            unidade_estoque='BR',
            unidade_compra_padrao='BR',
            unidades_compra_permitidas=[],
        )

    def test_compra_dimensional_permite_metro_e_barra(self):
        allowed = _allowed_unidades_negociacao(self.produto, 'compra')
        self.assertIn('M', allowed)
        self.assertIn('BR', allowed)
