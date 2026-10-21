"""Painel de rastreabilidade: códigos legíveis (heat number da corrida, número do CF)."""

from datetime import date

from django.test import TestCase

from apps.cadastros.models import Fornecedor
from apps.corridas.models import Corrida
from apps.produtos.models import Produto
from apps.produtos.painel_rastreabilidade import montar_painel_rastreabilidade
from apps.qualidade.models import (
    CertificadoFornecedorEntrada,
    ItemCertificadoFornecedorEntrada,
)


class PainelRastreabilidadeCorridasTests(TestCase):
    def setUp(self):
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Forn Rastreabilidade',
            cnpj='22.222.222/0001-99',
        )
        self.produto = Produto.objects.create(
            descricao='VALVULA ESFERA INOX 304',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='RAST-CF-001',
            unidade='PC',
        )
        # heat number real do cliente, não o id da linha
        self.corrida = Corrida.objects.create(
            numero='7287',
            produto=self.produto,
            fornecedor=self.fornecedor,
            data_recebimento=date(2026, 10, 1),
        )

    def _linha_corrida(self) -> dict:
        return montar_painel_rastreabilidade(self.produto)['corridas'][0]

    def test_sem_cf_devolve_codigo_e_cf_vazio(self):
        linha = self._linha_corrida()
        self.assertEqual(linha['codigo'], '7287')
        self.assertFalse(linha['possui_cf'])
        self.assertIsNone(linha['cf_numero'])

    def test_cf_aparece_com_numero_em_vez_de_booleano(self):
        cf = CertificadoFornecedorEntrada.objects.create(
            numero_certificado_fornecedor='CF-2026-0001',
            fornecedor=self.fornecedor,
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            produto=self.produto,
            corrida=self.corrida.numero,
            lote='L-9',
            ativo=True,
        )
        linha = self._linha_corrida()
        self.assertTrue(linha['possui_cf'])
        self.assertEqual(linha['cf_numero'], 'CF-2026-0001')
        self.assertEqual(linha['lote'], 'L-9')

    def test_cf_sem_numero_mantem_possui_cf_verdadeiro(self):
        cf = CertificadoFornecedorEntrada.objects.create(
            numero_certificado_fornecedor='',
            fornecedor=self.fornecedor,
        )
        ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            produto=self.produto,
            corrida=self.corrida.numero,
            ativo=True,
        )
        linha = self._linha_corrida()
        self.assertTrue(linha['possui_cf'])
        self.assertIsNone(linha['cf_numero'])
