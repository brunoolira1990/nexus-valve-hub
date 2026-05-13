"""Garante que produto/prévia não exijam whitelist de polegadas/roscas/schedules na família."""

import uuid
from decimal import Decimal

from django.test import TestCase

from apps.produtos.models import (
    FamiliaProduto,
    Polegada,
    Produto,
    RoscaConexao,
    ScheduleEspessura,
)
from apps.produtos.serializers import PreviewCodigoSerializer, ProdutoSerializer


def _mk_polegada_nps(slug: str, valor: str, desc: str) -> Polegada:
    co = (f'n{slug}')[:8]
    return Polegada.objects.create(
        tipo_medida=Polegada.TipoMedida.NPS,
        codigo=co[:4],
        codigo_oficial=co,
        descricao=desc[:64],
        valor_decimal=Decimal(valor),
    )


class ProdutoSemWhitelistFamiliaTests(TestCase):
    """Casos luva (rosca+NPS), flange (schedule+NPS), OD, espigão×flange e erros de obrigatoriedade/tipo."""

    def setUp(self):
        slug = uuid.uuid4().hex[:5]

        self.pol_half = _mk_polegada_nps(f'a{slug}', '0.5', f'1/2" NPS {slug}')
        self.pol_six = _mk_polegada_nps(f'b{slug}', '6', f'6" NPS {slug}')
        self.pol_four = _mk_polegada_nps(f'c{slug}', '4', f'4" NPS {slug}')
        self.pol_three = _mk_polegada_nps(f'd{slug}', '3', f'3" NPS {slug}')
        co_od = (f'o{slug}')[:8]
        self.pol_od = Polegada.objects.create(
            tipo_medida=Polegada.TipoMedida.OD,
            codigo=co_od[:4],
            codigo_oficial=co_od,
            descricao=f'OD {slug}'[:64],
            valor_decimal=Decimal('1'),
        )
        self.rosca = RoscaConexao.objects.create(codigo=f'BSP{slug}'[:16], descricao='BSP')
        self.sched = ScheduleEspessura.objects.create(codigo_schedule=f'S40{slug}', descricao='SCH 40')

        self.fam_luva = FamiliaProduto.objects.create(
            codigo_figura=f'LU{slug}',
            descricao_base='LUVA AÇO INOX 316 3000#',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS_X_ROSCA,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.fam_flange = FamiliaProduto.objects.create(
            codigo_figura=f'FL{slug}',
            descricao_base='FLANGE SW AÇO RF',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS_SCHEDULE,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.fam_esp = FamiliaProduto.objects.create(
            codigo_figura=f'ES{slug}',
            descricao_base='ESP x FL',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ESPIGAO_FLANGE_NPS,
            tipo_dimensional=FamiliaProduto.TipoDimensional.ESPIGAO_X_FLANGE,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.fam_od = FamiliaProduto.objects.create(
            codigo_figura=f'OD{slug}',
            descricao_base='PEÇA OD',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.OD_POLEGADA,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )

    def test_preview_luva_rosca_pol_sem_whitelist_familia(self):
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_luva.id,
                'rosca_conexao_id': self.rosca.id,
                'polegada_principal_ref_id': self.pol_half.id,
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        d = ser.validated_data
        blob = (d.get('_mensagem') or '') + (d.get('_descricao') or '')
        self.assertNotIn('Configure as polegadas permitidas', blob)
        self.assertTrue(d.get('_codigo'))
        desc = d.get('_descricao') or ''
        self.assertIn('BSP', desc)
        self.assertIn('LUVA ACO INOX 316 3000#', desc)
        self.assertRegex(desc, r'1/2')

    def test_expand_siglas_valvula_descricao(self):
        from apps.produtos.codigo_produto import expandir_siglas_valvula_descricao_base

        self.assertEqual(
            expandir_siglas_valvula_descricao_base('VEM WCB PP TP'),
            'VALVULA ESFERA MONOBLOCO WCB PP TP',
        )
        self.assertEqual(
            expandir_siglas_valvula_descricao_base('VEB SI CF8 PP TR FLANGEADA ANSI 150#'),
            'VALVULA ESFERA BIPARTIDA SI CF8 PP TR FLANGEADA ANSI 150#',
        )
        self.assertEqual(
            expandir_siglas_valvula_descricao_base('VET CF8M PP TP BSP'),
            'VALVULA ESFERA TRIPARTIDA CF8M PP TP BSP',
        )

    def test_preview_descricao_valvula_expandida(self):
        slug = uuid.uuid4().hex[:5]
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'V{slug}',
            descricao_base='VEM WCB PP TP',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        pol = _mk_polegada_nps(f'v{slug}', '2', f'2" NPS {slug}')
        ser = PreviewCodigoSerializer(
            data={'familia_id': fam.id, 'polegada_principal_ref_id': pol.id},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        desc = ser.validated_data.get('_descricao') or ''
        self.assertIn('VALVULA ESFERA MONOBLOCO', desc)
        self.assertNotIn('VEM ', desc)

    def test_create_produto_interno_luva_sem_whitelist(self):
        pser = ProdutoSerializer(
            data={
                'modo_codigo': Produto.ModoCodigo.INTERNO,
                'familia_id': self.fam_luva.id,
                'rosca_conexao_id': self.rosca.id,
                'polegada_principal_ref_id': self.pol_half.id,
                'descricao': 'x',
                'material': '',
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(pser.is_valid(), pser.errors)
        prod = pser.save()
        self.assertTrue((prod.codigo_completo or '').strip())
        self.assertTrue((prod.descricao or '').strip())

    def test_preview_flange_schedule_pol_sem_whitelist(self):
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_flange.id,
                'schedule_ref_id': self.sched.id,
                'polegada_principal_ref_id': self.pol_six.id,
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        blob = (ser.validated_data.get('_mensagem') or '') + (ser.validated_data.get('_descricao') or '')
        self.assertNotIn('Configure as polegadas permitidas', blob)
        self.assertIn('SCH 40', ser.validated_data.get('_descricao') or '')
        desc = ser.validated_data.get('_descricao') or ''
        self.assertIn('FLANGE SW ACO RF', desc)
        self.assertRegex(desc, r'6["\u201d]')

    def test_polegada_obrigatoria_sem_mensagem_whitelist(self):
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_luva.id,
                'rosca_conexao_id': self.rosca.id,
            },
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('polegada_principal_ref_id', ser.errors)
        self.assertNotIn('Configure as polegadas permitidas', str(ser.errors))
        self.assertIn('Informe a polegada principal', str(ser.errors))

    def test_nps_esperado_rejeita_polegada_od(self):
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_luva.id,
                'rosca_conexao_id': self.rosca.id,
                'polegada_principal_ref_id': self.pol_od.id,
            },
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('polegada_principal_ref_id', ser.errors)
        self.assertIn('NPS', str(ser.errors))
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_od.id,
                'polegada_principal_ref_id': self.pol_od.id,
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_espigao_flange_codigo_com_e_e_f(self):
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': self.fam_esp.id,
                'polegada_principal_ref_id': self.pol_four.id,
                'polegada_secundaria_ref_id': self.pol_three.id,
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        codigo = ser.validated_data.get('_codigo') or ''
        self.assertIn('E', codigo)
        self.assertIn('F', codigo)

    def test_preview_reducao_sem_acento_descricao_base(self):
        slug = uuid.uuid4().hex[:5]
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'RC{slug}',
            descricao_base='REDUÇÃO CONCENTRICA ACO CARBONO',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_DUAS_POLEGADAS,
            tipo_dimensional=FamiliaProduto.TipoDimensional.REDUCAO_NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        sched = ScheduleEspessura.objects.create(codigo_schedule=f'RS{slug}', descricao='SCH 40')
        ser = PreviewCodigoSerializer(
            data={
                'familia_id': fam.id,
                'schedule_ref_id': sched.id,
                'polegada_principal_ref_id': self.pol_six.id,
                'polegada_secundaria_ref_id': self.pol_half.id,
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        desc = ser.validated_data.get('_descricao') or ''
        self.assertIn('REDUCAO CONCENTRICA', desc)
        self.assertNotIn('Ç', desc)
        self.assertIn('"', desc)
        self.assertIn(' X ', desc)
