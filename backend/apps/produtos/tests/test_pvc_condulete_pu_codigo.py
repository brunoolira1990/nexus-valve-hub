"""PVC (DN/mm), condulete (bitola) e PU (OD mm) — código e descrição sem NPS/schedule industrial."""

import uuid
from decimal import Decimal

from django.test import TestCase

from apps.produtos.codigo_produto import montar_codigo_interno, montar_descricao_sugerida
from apps.produtos.dimensional_regra import requisitos_efetivos_produto, validar_tipo_dimensional_x_regra
from apps.produtos.models import FamiliaProduto, Polegada, RoscaConexao
from apps.produtos.serializers import PreviewCodigoSerializer, ProdutoSerializer


class PvcConduletePuCodigoTests(TestCase):
    def setUp(self):
        slug = uuid.uuid4().hex[:6]
        self.pol_34 = Polegada.objects.create(
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='05',
            codigo_oficial='05',
            descricao='3/4"',
            valor_decimal=Decimal('0.75'),
        )
        self.rosca_n = RoscaConexao.objects.create(codigo='N', descricao='NPT')

        self.fam_cotovelo = FamiliaProduto.objects.create(
            codigo_figura='0199',
            descricao_base='COTOVELO 45° PVC MARRON',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_DN_MM,
            tipo_dimensional=FamiliaProduto.TipoDimensional.DN_MM,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.fam_luva_red = FamiliaProduto.objects.create(
            codigo_figura='0202',
            descricao_base='LUVA REDUCAO PVC MARRON',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_DN_MM_REDUCAO,
            tipo_dimensional=FamiliaProduto.TipoDimensional.DN_MM_REDUCAO,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.fam_condulete = FamiliaProduto.objects.create(
            codigo_figura='0198',
            descricao_base='ADAPTADOR CONDULETE PVC',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_BITOLA_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.BITOLA_POLEGADA,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )

    def test_pvc_dn_simples_codigo_e_descricao(self):
        cod = montar_codigo_interno(
            self.fam_cotovelo,
            rosca=None,
            schedule=None,
            polegada_principal=None,
            polegada_secundaria=None,
            od_mm=Decimal('25'),
            espessura_mm=None,
        )
        self.assertEqual(cod, '0199.025')
        desc = montar_descricao_sugerida(
            self.fam_cotovelo,
            rosca=None,
            schedule=None,
            polegada_principal=None,
            polegada_secundaria=None,
            od_mm=Decimal('25'),
        )
        self.assertIn('25MM', desc)
        self.assertIn('COTOVELO', desc)

    def test_pvc_reducao_codigo_e_descricao(self):
        cod = montar_codigo_interno(
            self.fam_luva_red,
            rosca=None,
            schedule=None,
            polegada_principal=None,
            polegada_secundaria=None,
            od_mm=Decimal('50'),
            espessura_mm=Decimal('25'),
        )
        self.assertEqual(cod, '0202.050025')
        desc = montar_descricao_sugerida(
            self.fam_luva_red,
            rosca=None,
            schedule=None,
            polegada_principal=None,
            polegada_secundaria=None,
            od_mm=Decimal('50'),
            espessura_mm=Decimal('25'),
        )
        self.assertRegex(desc.upper(), r'50MM\s+X\s+25MM')

    def test_condulete_bitola_codigo(self):
        cod = montar_codigo_interno(
            self.fam_condulete,
            rosca=None,
            schedule=None,
            polegada_principal=self.pol_34,
            polegada_secundaria=None,
        )
        self.assertEqual(cod, '0198.05')
        desc = montar_descricao_sugerida(
            self.fam_condulete,
            rosca=None,
            schedule=None,
            polegada_principal=self.pol_34,
            polegada_secundaria=None,
        )
        self.assertIn('3/4', desc)

    def test_pvc_nao_exige_schedule(self):
        req = requisitos_efetivos_produto(self.fam_cotovelo)
        self.assertFalse(req['usa_schedule'])

    def test_validacao_dn_mm_nao_aceita_schedule_rule(self):
        msg = validar_tipo_dimensional_x_regra(
            tipo_dimensional=FamiliaProduto.TipoDimensional.DN_MM,
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_POLEGADA,
        )
        self.assertIsNotNone(msg)

    def test_preview_pvc(self):
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_cotovelo.id,
                'od_mm': '25',
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data.get('_codigo'), '0199.025')

    def test_create_produto_pvc_reducao_normaliza_maior_menor(self):
        pser = ProdutoSerializer(
            data={
                'modo_codigo': 'INTERNO',
                'familia_id': self.fam_luva_red.id,
                'od_mm': '25',
                'espessura_mm': '50',
                'descricao': 'x',
                'material': '',
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(pser.is_valid(), pser.errors)
        prod = pser.save()
        self.assertEqual(prod.codigo_completo, '0202.050025')
        self.assertEqual(prod.od_mm, Decimal('50'))
        self.assertEqual(prod.espessura_mm, Decimal('25'))
