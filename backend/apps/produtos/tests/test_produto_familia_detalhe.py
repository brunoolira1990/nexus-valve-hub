"""Contrato da ficha de produto: o retrieve devolve a Família inteira; a listagem continua no resumo."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.produtos.models import FamiliaProduto, Produto

CHAVES_RESUMO = {'id', 'codigo_figura', 'descricao_base', 'nome'}

# Chaves de que os cards espelhados da Edição dependem (Padrões, Requisitos, Polegadas, Qualidade).
CHAVES_FAMILIA_COMPLETA = {
    'tipo_regra_codigo',
    'tipo_dimensional',
    'categoria_produto',
    'requisitos_produto',
    'material_vedacao',
    'exige_certificado_qualidade',
    'unidades_venda_permitidas',
    'unidades_compra_permitidas',
}


class FamiliaDetalheDaFichaTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('ficha_fam', 'ficha_fam@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        sufixo = uuid.uuid4().hex[:6].upper()
        self.familia = FamiliaProduto.objects.create(
            codigo_figura=f'M{sufixo}',
            descricao_base='MANOMETRO GLICERINA',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.MANOMETRO,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
            material_vedacao='PTFE',
            exige_certificado_qualidade=True,
        )
        self.produto = Produto.objects.create(
            familia=self.familia,
            descricao='MANOMETRO GLICERINA 100MM 0 A 16BAR',
            modo_codigo=Produto.ModoCodigo.INTERNO,
            codigo_completo=f'M{sufixo}.01',
            unidade='PC',
            ncm='90261000',
        )

    def test_retrieve_devolve_a_familia_completa_com_as_chaves_do_resumo(self):
        resp = self.client.get(f'/api/produtos/{self.produto.id}/')
        self.assertEqual(resp.status_code, 200)
        detalhes = resp.json()['familia_detalhes']
        self.assertTrue(CHAVES_RESUMO <= set(detalhes), CHAVES_RESUMO - set(detalhes))
        self.assertTrue(CHAVES_FAMILIA_COMPLETA <= set(detalhes), CHAVES_FAMILIA_COMPLETA - set(detalhes))
        self.assertEqual(detalhes['id'], self.familia.id)
        self.assertEqual(detalhes['nome'], f'{self.familia.codigo_figura} — MANOMETRO GLICERINA')

    def test_requisitos_produto_do_detalhe_tem_a_flag_que_o_card_manometro_usa(self):
        detalhes = self.client.get(f'/api/produtos/{self.produto.id}/').json()['familia_detalhes']
        requisitos = detalhes['requisitos_produto']
        self.assertTrue(requisitos['exige_diametro_mostrador_mm'])
        self.assertTrue(requisitos['usa_polegada_principal'])
        self.assertEqual(detalhes['tipo_dimensional'], 'MANOMETRO')

    def test_listagem_continua_com_resumo_de_quatro_chaves(self):
        # Assinatura da listagem: se alguém reusar a família completa aqui, o payload de cada
        # linha cresce e o teste negativo abaixo falha — é o contrato que a UI de lista espera.
        resp = self.client.get('/api/produtos/', {'search': self.produto.codigo_completo, 'limit': 20})
        self.assertEqual(resp.status_code, 200)
        corpo = resp.json()
        linhas = corpo if isinstance(corpo, list) else corpo.get('results', [])
        linha = next(item for item in linhas if item['id'] == self.produto.id)
        self.assertEqual(set(linha['familia_detalhes']), CHAVES_RESUMO)

    def test_produto_sem_familia_continua_nulo_no_detalhe(self):
        sem_familia = Produto.objects.create(
            descricao='PARAFUSO AV10',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'SEMFAM{uuid.uuid4().hex[:5]}',
            unidade='PC',
        )
        detalhes = self.client.get(f'/api/produtos/{sem_familia.id}/').json()['familia_detalhes']
        self.assertIsNone(detalhes)
