"""Teste pontual — CST 20 / ICMS20 com redução de base."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.fiscal.nfe_cbenef_sp import CBENEF_SEM_CODIGO_LITERAL
from apps.fiscal.nfe_icms_calculo import calcular_base_valor_icms_saida
from apps.fiscal.nfe_saida_atualizar_impostos import _diff_snapshots
from apps.fiscal.nfe_saida_xml_nfelib import _build_det, _build_icms


class NFeIcmsCst20Tests(SimpleTestCase):
    def test_calculo_base_reduzida_cst20(self):
        base, valor = calcular_base_valor_icms_saida(
            Decimal('1600.00'),
            Decimal('12.00'),
            reducao_bc_pct=Decimal('33.3333'),
            cst_icms='20',
        )
        self.assertEqual(base, Decimal('1066.67'))
        self.assertEqual(valor, Decimal('128.00'))

    def test_calculo_regra_real_sp_sp_84818095(self):
        """NCM 84818095 SP→SP: redução 51,1100%, alíquota 18%, base R$ 5.000."""
        base, valor = calcular_base_valor_icms_saida(
            Decimal('5000.00'),
            Decimal('18.00'),
            reducao_bc_pct=Decimal('51.1100'),
            cst_icms='20',
        )
        self.assertEqual(base, Decimal('2444.50'))
        self.assertEqual(valor, Decimal('440.01'))

    def test_cst00_sem_reducao(self):
        base, valor = calcular_base_valor_icms_saida(
            Decimal('400.00'),
            Decimal('18.00'),
            cst_icms='00',
        )
        self.assertEqual(base, Decimal('400.00'))
        self.assertEqual(valor, Decimal('72.00'))

    def test_build_icms20_no_xml(self):
        snap = {
            'origem_mercadoria': '0',
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
        }
        linha = {'v_prod': Decimal('5000.00')}
        icms_wrap = _build_icms(snap, linha)

        self.assertIsNone(icms_wrap.ICMS00)
        self.assertIsNotNone(icms_wrap.ICMS20)
        icms20 = icms_wrap.ICMS20
        self.assertEqual(icms20.CST, '20')
        self.assertEqual(str(icms20.modBC), '3')
        self.assertEqual(str(icms20.pRedBC), '51.1100')
        self.assertEqual(str(icms20.vBC), '2444.50')
        self.assertEqual(str(icms20.pICMS), '18.00')
        self.assertEqual(str(icms20.vICMS), '440.01')

    def test_preview_diff_mostra_reducao_e_base(self):
        antes = {
            'cst_icms': '20',
            'aliquota_icms': '18.00',
            'base_icms': '5000.00',
            'valor_icms': '900.00',
        }
        depois = {
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
        }
        alteracoes = {a['campo']: a for a in _diff_snapshots(antes, depois)}
        self.assertEqual(alteracoes['reducao_bc_icms']['depois'], '51.1100')
        self.assertEqual(alteracoes['base_icms']['depois'], '2444.50')
        self.assertEqual(alteracoes['valor_icms']['antes'], '900.00')
        self.assertEqual(alteracoes['valor_icms']['depois'], '440.01')

    def test_build_icms00_cst00(self):
        snap = {
            'cst_icms': '00',
            'base_icms': '400.00',
            'aliquota_icms': '18.00',
            'valor_icms': '72.00',
        }
        linha = {'v_prod': Decimal('400.00')}
        icms_wrap = _build_icms(snap, linha)

        self.assertIsNotNone(icms_wrap.ICMS00)
        self.assertIsNone(icms_wrap.ICMS20)
        self.assertEqual(icms_wrap.ICMS00.CST, '00')

    def test_icms20_sem_cbenef_quando_regra_vazia(self):
        snap = {
            'origem_mercadoria': '0',
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
            'codigo_beneficio_icms': '',
        }
        linha = {
            'n_item': '1',
            'c_prod': '2043.05',
            'x_prod': 'Item teste',
            'ncm': '84818095',
            'cfop': '5102',
            'u_com': 'PC',
            'q_com': '10',
            'v_un_com': '500.00',
            'v_prod': '5000.00',
            'snapshot_fiscal': snap,
        }
        det = _build_det(linha)
        self.assertIsNone(det.prod.cBenef)
        self.assertIsNotNone(det.imposto.ICMS.ICMS20)
        icms20 = det.imposto.ICMS.ICMS20
        self.assertIsNone(icms20.vICMSDeson)
        self.assertIsNone(icms20.motDesICMS)

    def test_icms20_com_cbenef_quando_regra_preenchida(self):
        snap = {
            'origem_mercadoria': '0',
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
            'codigo_beneficio_icms': 'SP123456',
        }
        linha = {
            'n_item': '1',
            'c_prod': '2043.05',
            'x_prod': 'Item teste',
            'ncm': '84818095',
            'cfop': '5102',
            'u_com': 'PC',
            'q_com': '10',
            'v_un_com': '500.00',
            'v_prod': '5000.00',
            'snapshot_fiscal': snap,
        }
        det = _build_det(linha)
        self.assertEqual(det.prod.cBenef, 'SP123456')

    def test_icms20_com_sem_cbenef_literal(self):
        """Marcador SEM CBENEF NÃO deve serializar (cStat 946)."""
        snap = {
            'origem_mercadoria': '0',
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
            'codigo_beneficio_icms': CBENEF_SEM_CODIGO_LITERAL,
        }
        linha = {
            'n_item': '1',
            'c_prod': '2043.05',
            'x_prod': 'Item teste',
            'ncm': '84818095',
            'cfop': '5102',
            'u_com': 'PC',
            'q_com': '10',
            'v_un_com': '500.00',
            'v_prod': '5000.00',
            'snapshot_fiscal': snap,
        }
        det = _build_det(linha)
        self.assertIsNone(det.prod.cBenef)
        icms20 = det.imposto.ICMS.ICMS20
        self.assertEqual(icms20.CST, '20')
        self.assertEqual(str(icms20.pRedBC), '51.1100')
        self.assertEqual(str(icms20.vBC), '2444.50')
        self.assertEqual(str(icms20.vICMS), '440.01')

    def test_icms20_nao_envia_desoneracao_sem_motivo(self):
        snap = {
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
            'motivo_desoneracao_icms': '',
            'valor_icms_deson': '100.00',
        }
        icms_wrap = _build_icms(snap, {'v_prod': '5000.00'})
        icms20 = icms_wrap.ICMS20
        self.assertIsNone(icms20.vICMSDeson)
        self.assertIsNone(icms20.motDesICMS)
