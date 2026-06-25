"""Testes unitários — escala e clip visual do infCpl no DANFE (sem XML)."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.nfe_integracao.danfe_bfr_infcpl import (
    INFCPL_FONT_BASE_FACTOR,
    escala_efetiva_infcpl,
)


class DanfeBfrInfcplUnitTests(SimpleTestCase):
    def test_fonte_base_reduzida_entre_6_e_7_5pt(self):
        # BFR FONT_SIZE_CONT típico com FontSize.SMALL ≈ 7pt
        base = 7.0
        efetiva = escala_efetiva_infcpl(base, 1.0)
        self.assertGreaterEqual(efetiva, 5.0)
        self.assertLessEqual(efetiva, 7.0)
        self.assertAlmostEqual(efetiva, base * INFCPL_FONT_BASE_FACTOR)

    def test_auto_shrink_reduz_fonte(self):
        base = 7.0
        cheia = escala_efetiva_infcpl(base, 1.0)
        reduzida = escala_efetiva_infcpl(base, 0.46)
        self.assertLess(reduzida, cheia)
