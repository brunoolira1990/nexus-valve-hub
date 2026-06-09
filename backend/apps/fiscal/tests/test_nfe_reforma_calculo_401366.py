"""ERP 4.0.13.6.6 — Cálculo Reforma Tributária no snapshot NF-e rascunho."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe, preparar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_reforma_calculo import (
    aplicar_reforma_tributaria_item,
    normalizar_percentual_reforma,
    status_reforma_snapshot,
)
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa, _regra_sp_pa
from apps.fiscal.tests.test_nfe_saida_faturamento import _cnpj, _faturamento_pronto, _produto
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.regras_fiscais.models import RegraFiscalSaida
from apps.regras_fiscais.reforma_tributaria_config import normalizar_reforma_tributaria


class ReformaPercentualParsingTests(TestCase):
    def test_virgula_pt_br(self):
        self.assertEqual(normalizar_percentual_reforma('0,1'), Decimal('0.1'))
        self.assertEqual(normalizar_percentual_reforma('0,9'), Decimal('0.9'))

    def test_ponto_decimal(self):
        self.assertEqual(normalizar_percentual_reforma('0.1'), Decimal('0.1'))

    def test_normalizar_reforma_salva_ponto(self):
        norm = normalizar_reforma_tributaria(
            {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_ibs_estadual': '0,1',
                'aliquota_cbs': '0,9',
            },
        )
        self.assertEqual(norm['aliquota_ibs_estadual'], '0.1')
        self.assertEqual(norm['aliquota_cbs'], '0.9')


class ReformaCalculoItemTests(TestCase):
    def test_calculo_500_reais(self):
        bloco = aplicar_reforma_tributaria_item(
            {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_ibs_estadual': '0,1',
                'aliquota_cbs': '0,9',
            },
            valor_produto=Decimal('500'),
        )
        self.assertIsNotNone(bloco)
        self.assertEqual(bloco['valor_ibs_estadual'], '0.50')
        self.assertEqual(bloco['valor_cbs'], '4.50')
        self.assertEqual(bloco['valor_total_ibs_cbs'], '5.00')
        self.assertEqual(status_reforma_snapshot(bloco), 'CALCULADA')

    def test_aliquota_sem_virgula_zero_indevido(self):
        bloco = aplicar_reforma_tributaria_item(
            {'cst_ibs_cbs': '000', 'classificacao_tributaria': '000001', 'aliquota_cbs': '0,9'},
            valor_produto=Decimal('100'),
        )
        self.assertEqual(bloco['valor_cbs'], '0.90')


class NFeAtualizarFiscalReforma401366Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe366', 'nfe366@test.com', 'x')
        regra = _regra_sp_pa()
        regra.reforma_tributaria = {
            'cst_ibs_cbs': '000',
            'classificacao_tributaria': '000001',
            'aliquota_ibs_estadual': '0,1',
            'aliquota_cbs': '0,9',
        }
        regra.save(update_fields=['reforma_tributaria'])

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_atualizar_fiscal_calcula_reforma(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': 'AV',
            'bairro': 'X',
            'complemento': '',
        }
        nf, nf_item = _nf_pa()
        qtd = nf_item.quantidade
        valor = nf_item.valor
        prod_id = nf_item.produto_id

        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        ref = (nf_item.snapshot_fiscal or {}).get('reforma_tributaria') or {}

        self.assertEqual(ref.get('aliquota_cbs'), '0.9')
        self.assertEqual(ref.get('aliquota_ibs_estadual'), '0.1')
        self.assertEqual(ref.get('valor_cbs'), '4.50')
        self.assertEqual(ref.get('valor_ibs_estadual'), '0.50')
        self.assertEqual(ref.get('valor_total_ibs_cbs'), '5.00')
        self.assertEqual(nf_item.quantidade, qtd)
        self.assertEqual(nf_item.valor, valor)
        self.assertEqual(nf_item.produto_id, prod_id)

        prev = preparar_atualizacao_impostos_nfe(nf)
        info = str(prev.get('diagnosticos', [{}])[0].get('informacao', ''))
        self.assertIn('Reforma calculada', info)
        self.assertIn('4.50', info)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_validacao_sem_pendencia_reforma_calculada(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf = NFeSaida.objects.prefetch_related('itens').get(pk=nf.pk)
        val = validar_nfe_saida_para_emissao(nf)
        codigos = [
            p.get('codigo')
            for g in val.get('grupos', {}).values()
            for p in g
        ]
        self.assertNotIn('REFORMA_ALIQUOTA_SEM_VALOR', codigos)
