"""Rótulos de exibição do ProdutoSerializer: o payload ganha *_display e os ids continuam iguais."""

from decimal import Decimal

from django.test import TestCase

from apps.produtos.models import (
    FamiliaProduto,
    Material,
    Polegada,
    Produto,
    RoscaConexao,
    ScheduleEspessura,
)
from apps.produtos.rotulos import rotulo_de_choices
from apps.produtos.serializers import ProdutoSerializer


def _produto(codigo: str, **campos) -> Produto:
    base = {
        'descricao': 'FLANGE CEGO ACO CARBONO ANSI 150# RF',
        'modo_codigo': Produto.ModoCodigo.MANUAL,
        'codigo_completo': codigo,
        'unidade': 'PC',
    }
    base.update(campos)
    return Produto.objects.create(**base)


def _familia(codigo_figura: str) -> FamiliaProduto:
    return FamiliaProduto.objects.create(
        codigo_figura=codigo_figura,
        descricao_base='FLANGE CEGO ACO CARBONO ANSI 150# RF',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
    )


class ProdutoSerializerRotulosTests(TestCase):
    def test_choices_retornam_rotulo_oficial_sem_perder_o_codigo(self):
        produto = _produto(
            'ROT-001',
            tipo_fisico='BARRA_CHATA',
            tipo_controle_unidade='DIMENSIONAL',
            tipo_composicao_fisica='PECA_KG',
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['tipo_fisico'], 'BARRA_CHATA')
        self.assertEqual(data['tipo_fisico_display'], 'Barra chata')
        self.assertEqual(data['tipo_controle_unidade_display'], 'Dimensional')
        self.assertEqual(
            data['tipo_composicao_fisica_display'], 'Peça/chapa (peso em kg)'
        )

    def test_efetivo_calculado_tambem_ganha_rotulo(self):
        # Sem família e sem tipo físico próprio: o efetivo cai no default do model (PECA).
        data = ProdutoSerializer(_produto('ROT-002')).data
        self.assertIsNone(data['tipo_fisico_display'])
        self.assertEqual(data['tipo_fisico_efetivo'], 'PECA')
        self.assertEqual(data['tipo_fisico_efetivo_display'], 'Peça')
        self.assertEqual(data['tipo_controle_unidade_efetivo_display'], 'Peça')

    def test_familia_detalhes_traz_id_e_nome_e_familia_id_continua_numero(self):
        familia = _familia('9913')
        produto = _produto('ROT-003', familia=familia)
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['familia_id'], familia.id)
        self.assertIsInstance(data['familia_id'], int)
        self.assertEqual(
            data['familia_detalhes'],
            {
                'id': familia.id,
                'codigo_figura': '9913',
                'descricao_base': 'FLANGE CEGO ACO CARBONO ANSI 150# RF',
                'nome': '9913 — FLANGE CEGO ACO CARBONO ANSI 150# RF',
            },
        )

    def test_produto_sem_familia_devolve_familia_detalhes_nulo(self):
        data = ProdutoSerializer(_produto('ROT-004')).data
        self.assertIn('familia_detalhes', data)
        self.assertIsNone(data['familia_detalhes'])
        self.assertIsNone(data['polegada_principal_ref_detalhes'])

    def test_polegada_rosca_schedule_detalhes_trazem_codigo_legivel(self):
        polegada = Polegada.objects.create(
            tipo_medida=Polegada.TipoMedida.NPS,
            codigo='01',
            codigo_oficial='01',
            descricao='1/2"',
            valor_decimal=Decimal('0.5'),
        )
        rosca = RoscaConexao.objects.create(codigo='BSP', descricao='BSP')
        schedule = ScheduleEspessura.objects.create(codigo_schedule='SCH40', descricao='SCH 40')
        produto = _produto(
            'ROT-005',
            polegada_principal_ref=polegada,
            rosca_conexao=rosca,
            schedule_ref=schedule,
        )
        data = ProdutoSerializer(produto).data
        nome_polegada = data['polegada_principal_ref_detalhes']['nome']
        self.assertIn('1/2"', nome_polegada)
        self.assertTrue(nome_polegada.startswith('NPS 01'))
        self.assertEqual(data['polegada_principal_ref_id'], polegada.id)
        self.assertEqual(
            data['rosca_conexao_detalhes'],
            {'id': rosca.id, 'codigo': 'BSP', 'descricao': 'BSP'},
        )
        self.assertEqual(data['schedule_ref_detalhes']['codigo_schedule'], 'SCH40')

    def test_polegada_das_dimensoes_tambem_ganha_resumo(self):
        od = Polegada.objects.create(
            tipo_medida=Polegada.TipoMedida.OD,
            codigo='55',
            codigo_oficial='55',
            descricao='1/2"',
            valor_decimal=Decimal('0.5'),
        )
        produto = _produto(
            'ROT-008',
            dim_aba_polegada_ref=od,
            dim_espessura_polegada_ref=od,
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['dim_aba_polegada_ref'], od.id)
        self.assertEqual(data['dim_aba_polegada_ref_detalhes']['id'], od.id)
        self.assertIn('1/2"', data['dim_aba_polegada_ref_detalhes']['nome'])
        self.assertIn('OD', data['dim_espessura_polegada_ref_detalhes']['nome'])

    def test_material_nome_vem_do_catalogo_quando_ha_fk(self):
        catalogo = Material.objects.create(
            nome='Aço Carbono A105',
            nome_curto='A105',
            categoria=Material.Categoria.ACO_CARBONO,
        )
        produto = _produto(
            'ROT-006',
            material_ref=catalogo,
            material='ACO CARBONO',
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['material'], 'ACO CARBONO')
        self.assertEqual(data['material_nome'], 'Aço Carbono A105')

    def test_material_nome_usa_o_rotulo_da_categoria_sem_fk(self):
        data = ProdutoSerializer(_produto('ROT-007', material='ACO CARBONO')).data
        self.assertEqual(data['material_nome'], 'Aço Carbono')
        self.assertIsNone(data['material_ref_detalhes'])

    def test_campo_sem_choices_nao_ganha_rotulo(self):
        # 'unidade' é CharField livre: não existe rótulo oficial a ser exibido.
        self.assertIsNone(rotulo_de_choices('produtos', 'produto', 'unidade', 'PC'))
        self.assertIsNone(rotulo_de_choices('produtos', 'produto', 'tipo_fisico', 'NAO_EXISTE'))
        self.assertIsNone(rotulo_de_choices('produtos', 'produto', 'tipo_fisico', ''))
