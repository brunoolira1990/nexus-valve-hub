from decimal import Decimal

from django.test import TestCase

from apps.produtos.codigo_produto import montar_codigo_interno, montar_descricao_sugerida
from apps.produtos.models import FamiliaProduto, Polegada, Produto
from apps.produtos.serializers import PreviewCodigoSerializer, ProdutoSerializer


class DescricaoPosicionavelTests(TestCase):
    def setUp(self):
        self.polegada = Polegada.objects.create(
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='01',
            codigo_oficial='01',
            descricao='1/2"',
            valor_decimal=Decimal('0.5'),
        )
        self.familia_template = FamiliaProduto.objects.create(
            codigo_figura='9901',
            descricao_base='MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA [P] BSP ESCALA 0 A 4 BAR',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.SIMPLES,
        )
        self.familia_legada = FamiliaProduto.objects.create(
            codigo_figura='9902',
            descricao_base='MANOMETRO SEM TOKEN',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.SIMPLES,
        )

    def test_polegada_principal_eh_inserida_no_meio_sem_duplicacao(self):
        descricao = montar_descricao_sugerida(
            self.familia_template,
            rosca=None,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
        )

        esperado = 'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP ESCALA 0 A 4 BAR'
        self.assertEqual(descricao, esperado)
        self.assertEqual(descricao.count('1/2"'), 1)
        self.assertNotIn('BAR 1/2"', descricao)

    def test_familia_sem_token_preserva_fallback_legado(self):
        descricao = montar_descricao_sugerida(
            self.familia_legada,
            rosca=None,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
        )

        self.assertEqual(descricao, 'MANOMETRO SEM TOKEN 1/2"')

    def test_codigo_dimensional_nao_compartilha_renderer_de_descricao(self):
        codigo_antes = montar_codigo_interno(
            self.familia_template,
            rosca=None,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
        )
        descricao = montar_descricao_sugerida(
            self.familia_template,
            rosca=None,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
        )

        self.assertEqual(codigo_antes, '9901.01')
        self.assertIn('1/2" BSP', descricao)

    def test_preview_e_persistencia_reaberta_mantem_descricao_posicionada(self):
        preview = PreviewCodigoSerializer(
            data={
                'familia_id': self.familia_template.id,
                'polegada_principal_ref_id': self.polegada.id,
            },
        )
        self.assertTrue(preview.is_valid(), preview.errors)
        descricao = preview.validated_data['_descricao']

        produto_ser = ProdutoSerializer(
            data={
                'modo_codigo': 'INTERNO',
                'familia_id': self.familia_template.id,
                'polegada_principal_ref_id': self.polegada.id,
                'descricao': descricao,
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(produto_ser.is_valid(), produto_ser.errors)
        produto = produto_ser.save()
        produto_reaberto = Produto.objects.get(pk=produto.pk)

        self.assertEqual(produto_reaberto.descricao, descricao)
        self.assertNotIn('BAR 1/2"', produto_reaberto.descricao)
        self.assertEqual(produto_reaberto.ncm, '')
