"""F0 — helper CST + regime para crédito/débito PIS/COFINS."""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.services.pis_cofins_credito import (
    classificar_regime_tributario,
    cst_pis_cofins_gera_credito,
    cst_pis_cofins_gera_debito,
    normalizar_cst_pis_cofins,
    regime_permite_credito_pis_cofins,
)


class PisCofinsCreditoHelperTest(SimpleTestCase):
    def test_normalizar_cst(self) -> None:
        self.assertEqual(normalizar_cst_pis_cofins('50'), '50')
        self.assertEqual(normalizar_cst_pis_cofins('5'), '05')
        self.assertEqual(normalizar_cst_pis_cofins('CST 51'), '51')

    def test_classificar_regime(self) -> None:
        self.assertEqual(classificar_regime_tributario('Lucro Real'), 'LUCRO_REAL')
        self.assertEqual(classificar_regime_tributario('Lucro Presumido'), 'LUCRO_PRESUMIDO')
        self.assertEqual(classificar_regime_tributario('Simples Nacional'), 'SIMPLES')
        self.assertEqual(classificar_regime_tributario(''), 'INDEFINIDO')

    def test_credito_exige_lucro_real_e_cst(self) -> None:
        self.assertTrue(cst_pis_cofins_gera_credito('50', regime_tributario='Lucro Real'))
        self.assertTrue(cst_pis_cofins_gera_credito('66', regime_classificado='LUCRO_REAL'))
        self.assertFalse(cst_pis_cofins_gera_credito('50', regime_tributario='Lucro Presumido'))
        self.assertFalse(cst_pis_cofins_gera_credito('50', regime_tributario='Simples Nacional'))
        self.assertFalse(cst_pis_cofins_gera_credito('01', regime_tributario='Lucro Real'))
        self.assertFalse(cst_pis_cofins_gera_credito('50', regime_tributario=''))

    def test_debito_cst_01_05(self) -> None:
        self.assertTrue(cst_pis_cofins_gera_debito('01'))
        self.assertTrue(cst_pis_cofins_gera_debito('05'))
        self.assertFalse(cst_pis_cofins_gera_debito('50'))
        self.assertFalse(cst_pis_cofins_gera_debito('99'))

    def test_regime_permite(self) -> None:
        self.assertTrue(regime_permite_credito_pis_cofins('LUCRO_REAL'))
        self.assertFalse(regime_permite_credito_pis_cofins('LUCRO_PRESUMIDO'))
        self.assertTrue(regime_permite_credito_pis_cofins('Lucro Real'))
