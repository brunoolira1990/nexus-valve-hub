from decimal import Decimal

from django.test import TestCase

from apps.produtos.codigo_produto import montar_codigo_interno, montar_descricao_sugerida
from apps.produtos.models import FamiliaProduto, Polegada, Produto, RoscaConexao
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
        self.rosca_bsp = RoscaConexao.objects.create(codigo='BSP', descricao='BSP')
        self.familia_manometro = FamiliaProduto.objects.create(
            codigo_figura='9904',
            descricao_base='MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANOMETRO,
        )
        self.familia_p_only = FamiliaProduto.objects.create(
            codigo_figura='9901',
            descricao_base='MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA [P] BSP',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.SIMPLES,
        )
        self.familia_completa = FamiliaProduto.objects.create(
            codigo_figura='9902',
            descricao_base=(
                'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA [P] BSP '
                'ESCALA [ESCALA] [UNIDADE] PONTEIRO [PONTEIRO] '
                'VIDRO [VIDRO] E CLASSE [CLASSE] C/ [FLUIDO] '
                'E CERTIFICACAO [CERTIFICACAO]'
            ),
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.SIMPLES,
        )
        self.familia_legada = FamiliaProduto.objects.create(
            codigo_figura='9903',
            descricao_base='MANOMETRO SEM TOKEN',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.SIMPLES,
        )

    @staticmethod
    def atributos_completos():
        return {
            'escala': '0 A 4',
            'unidade_escala': 'BAR',
            'ponteiro': 'MICROMETRICO',
            'vidro': 'SAFETY GLASS',
            'classe': 'A1',
            'fluido': 'GLICERINA',
            'certificacao': 'RBC INMETRO',
        }

    def render(self, familia, dimensoes=None):
        return montar_descricao_sugerida(
            familia,
            rosca=None,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
            dimensoes=dimensoes or {},
        )

    def render_manometro(self, dimensoes=None):
        return montar_descricao_sugerida(
            self.familia_manometro,
            rosca=self.rosca_bsp,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
            dimensoes=dimensoes or {},
        )

    def test_somente_polegada_principal_continua_funcionando(self):
        descricao = self.render(self.familia_p_only)

        self.assertEqual(descricao, 'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP')
        self.assertEqual(descricao.count('1/2"'), 1)

    def test_polegada_escala_e_unidade_sao_posicionadas(self):
        descricao = self.render(
            self.familia_completa,
            {'escala': '0 A 4', 'unidade_escala': 'BAR'},
        )

        self.assertIn('1/2" BSP ESCALA 0 A 4 BAR', descricao)
        self.assertEqual(descricao.count('0 A 4'), 1)
        self.assertEqual(descricao.count('BAR'), 1)

    def test_descricao_completa_de_manometro_respeita_ordem_do_template(self):
        descricao = self.render(self.familia_completa, self.atributos_completos())

        esperado = (
            'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP '
            'ESCALA 0 A 4 BAR PONTEIRO MICROMETRICO VIDRO SAFETY GLASS '
            'E CLASSE A1 C/ GLICERINA E CERTIFICACAO RBC INMETRO'
        )
        self.assertEqual(descricao, esperado)

    def test_atributo_opcional_vazio_remove_frase_inteira(self):
        descricao = self.render(
            self.familia_completa,
            {'escala': '0 A 4', 'unidade_escala': ''},
        )

        self.assertEqual(descricao, 'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP')
        for trecho in ('ESCALA', 'PONTEIRO', 'VIDRO', 'CLASSE', 'C/', 'CERTIFICACAO'):
            self.assertNotIn(trecho, descricao)

    def test_nenhum_atributo_e_duplicado(self):
        descricao = self.render(self.familia_completa, self.atributos_completos())

        for valor in ('1/2"', '0 A 4', 'BAR', 'MICROMETRICO', 'SAFETY GLASS', 'A1', 'GLICERINA', 'RBC INMETRO'):
            self.assertEqual(descricao.count(valor), 1, valor)
        self.assertNotIn('RBC INMETRO 1/2"', descricao)

    def test_familia_antiga_sem_tokens_preserva_fallback_legado(self):
        self.assertEqual(self.render(self.familia_legada), 'MANOMETRO SEM TOKEN 1/2"')

    def test_codigo_dimensional_nao_e_afetado_por_tokens_de_descricao(self):
        codigo = montar_codigo_interno(
            self.familia_completa,
            rosca=None,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
            dimensoes=self.atributos_completos(),
        )

        self.assertEqual(codigo, '9902.01')

    def test_preview_e_persistencia_reaberta_mantem_atributos_e_descricao(self):
        dimensoes = self.atributos_completos()
        preview = PreviewCodigoSerializer(
            data={
                'familia_id': self.familia_completa.id,
                'polegada_principal_ref_id': self.polegada.id,
                'dimensoes_json': dimensoes,
            },
        )
        self.assertTrue(preview.is_valid(), preview.errors)
        descricao = preview.validated_data['_descricao']

        produto_ser = ProdutoSerializer(
            data={
                'modo_codigo': 'INTERNO',
                'familia_id': self.familia_completa.id,
                'polegada_principal_ref_id': self.polegada.id,
                'descricao': descricao,
                'dimensoes_json': dimensoes,
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(produto_ser.is_valid(), produto_ser.errors)
        produto = produto_ser.save()
        produto_reaberto = Produto.objects.get(pk=produto.pk)

        self.assertEqual(produto_reaberto.descricao, descricao)
        self.assertEqual(produto_reaberto.dimensoes_json, dimensoes)
        self.assertEqual(produto_reaberto.ncm, '')

    def test_ncm_vazio_permanece_inalterado_ao_gerar_descricao(self):
        produto_ser = ProdutoSerializer(
            data={
                'modo_codigo': 'INTERNO',
                'familia_id': self.familia_completa.id,
                'polegada_principal_ref_id': self.polegada.id,
                'descricao': self.render(self.familia_completa, self.atributos_completos()),
                'dimensoes_json': self.atributos_completos(),
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(produto_ser.is_valid(), produto_ser.errors)
        produto = produto_ser.save()

        self.assertEqual(produto.ncm, '')
        self.assertEqual(produto.ncm_especifico, '')
        self.assertIn('1/2" BSP ESCALA 0 A 4 BAR', produto.descricao)

    def test_manometro_estrutural_sem_tokens_monta_descricao_completa(self):
        descricao = self.render_manometro(self.atributos_completos())

        esperado = (
            'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP '
            'ESCALA 0 A 4 BAR PONTEIRO MICROMETRICO VIDRO SAFETY GLASS '
            'E CLASSE A1 C/ GLICERINA E CERTIFICACAO RBC INMETRO'
        )
        self.assertEqual(descricao, esperado)

    def test_manometro_estrutural_minimo_nao_gera_fragmentos_vazios(self):
        descricao = self.render_manometro()

        self.assertEqual(descricao, 'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP')
        for trecho in ('ESCALA', 'PONTEIRO', 'VIDRO', 'CLASSE', 'C/', 'CERTIFICACAO'):
            self.assertNotIn(trecho, descricao)

    def test_manometro_estrutural_com_tokens_preserva_precedencia_legada(self):
        familia = FamiliaProduto.objects.create(
            codigo_figura='9905',
            descricao_base='MANOMETRO [P] BSP ESCALA [ESCALA] [UNIDADE]',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_ROSCA_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANOMETRO,
        )
        descricao = montar_descricao_sugerida(
            familia,
            rosca=self.rosca_bsp,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
            dimensoes={'escala': '0 A 4', 'unidade_escala': 'BAR'},
        )

        self.assertEqual(descricao, 'MANOMETRO 1/2" BSP ESCALA 0 A 4 BAR')
        self.assertEqual(descricao.count('1/2"'), 1)

    def test_produto_existente_com_descricao_persistida_nao_e_regenerado(self):
        descricao_historica = 'MANOMETRO HISTORICO 1/2" BSP'
        produto_ser = ProdutoSerializer(
            data={
                'modo_codigo': 'INTERNO',
                'familia_id': self.familia_manometro.id,
                'rosca_conexao_id': self.rosca_bsp.id,
                'polegada_principal_ref_id': self.polegada.id,
                'descricao': descricao_historica,
                'dimensoes_json': self.atributos_completos(),
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(produto_ser.is_valid(), produto_ser.errors)
        produto = produto_ser.save()

        self.assertEqual(produto.descricao, descricao_historica)
        self.assertEqual(produto.ncm, '')

    def test_manometro_exige_regra_de_codigo_compatível(self):
        from apps.produtos.dimensional_regra import validar_tipo_dimensional_x_regra

        mensagem = validar_tipo_dimensional_x_regra(
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANOMETRO,
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        )

        self.assertIn('Manômetro exige', mensagem or '')

    def test_requisitos_manometro_usam_polegada_e_rosca_sem_schedule(self):
        from apps.produtos.dimensional_regra import requisitos_efetivos_produto, tipo_medida_esperado_por_campo

        familia = self.familia_manometro
        requisitos = requisitos_efetivos_produto(familia)

        self.assertTrue(requisitos['usa_polegada_principal'])
        self.assertTrue(requisitos['usa_rosca_conexao'])
        self.assertFalse(requisitos['usa_schedule'])
        self.assertEqual(tipo_medida_esperado_por_campo(familia)['polegada_principal_ref_id'], Polegada.TipoMedida.NPS)

    def test_codigo_manometro_continua_compatível_com_regra_existente(self):
        codigo = montar_codigo_interno(
            self.familia_manometro,
            rosca=self.rosca_bsp,
            schedule=None,
            polegada_principal=self.polegada,
            polegada_secundaria=None,
            dimensoes=self.atributos_completos(),
        )

        self.assertEqual(codigo, '9904BSP.01')

    def test_ncm_e_codigo_nao_sao_alterados_por_descricao_manometro(self):
        descricao = self.render_manometro(self.atributos_completos())
        produto_ser = ProdutoSerializer(
            data={
                'modo_codigo': 'INTERNO',
                'familia_id': self.familia_manometro.id,
                'rosca_conexao_id': self.rosca_bsp.id,
                'polegada_principal_ref_id': self.polegada.id,
                'descricao': descricao,
                'dimensoes_json': self.atributos_completos(),
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
        )
        self.assertTrue(produto_ser.is_valid(), produto_ser.errors)
        produto = produto_ser.save()

        self.assertEqual(produto.codigo_completo, '9904BSP.01')
        self.assertEqual(produto.ncm, '')
        self.assertEqual(produto.ncm_especifico, '')

    def test_familias_legadas_relevantes_continuam_no_renderer_existente(self):
        self.assertEqual(self.render(self.familia_p_only), 'MANOMETRO 100MM TOTAL INOX 304 ROSCA RETA 1/2" BSP')
        self.assertEqual(self.render(self.familia_legada), 'MANOMETRO SEM TOKEN 1/2"')
