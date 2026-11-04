"""Testes da regra global de unidade de dureza nos PDFs de certificado.

`formatar_dureza_com_unidade` mora na camada compartilhada (apps.core.pdf.formatters)
e vale para todos os tipos de certificado: <100 → HRC, >=100 → HB, vazio → "".
"""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.core.pdf.formatters import formatar_dureza_com_unidade


class FormatardurezaComUnidadeTests(SimpleTestCase):
    def test_abaixo_de_100_e_hrc(self):
        self.assertEqual(formatar_dureza_com_unidade('33'), '33 HRC')
        self.assertEqual(formatar_dureza_com_unidade('29'), '29 HRC')
        self.assertEqual(formatar_dureza_com_unidade(33), '33 HRC')
        self.assertEqual(formatar_dureza_com_unidade(29), '29 HRC')
        self.assertEqual(formatar_dureza_com_unidade(Decimal('29')), '29 HRC')

    def test_de_100_para_cima_e_hb(self):
        self.assertEqual(formatar_dureza_com_unidade('153'), '153 HB')
        self.assertEqual(formatar_dureza_com_unidade('229'), '229 HB')
        self.assertEqual(formatar_dureza_com_unidade(153), '153 HB')
        self.assertEqual(formatar_dureza_com_unidade(229), '229 HB')

    def test_fronteira_de_100_e_limiar_inclusivo(self):
        self.assertEqual(formatar_dureza_com_unidade('99.9'), '99.9 HRC')
        self.assertEqual(formatar_dureza_com_unidade(99.9), '99.9 HRC')
        self.assertEqual(formatar_dureza_com_unidade('100'), '100 HB')
        self.assertEqual(formatar_dureza_com_unidade(100), '100 HB')

    def test_vazio_devolve_celula_sem_unidade_solta(self):
        self.assertEqual(formatar_dureza_com_unidade(None), '')
        self.assertEqual(formatar_dureza_com_unidade(''), '')
        self.assertEqual(formatar_dureza_com_unidade('   '), '')
        self.assertEqual(formatar_dureza_com_unidade({}), '')
        self.assertEqual(formatar_dureza_com_unidade([]), '')

    def test_nao_reinventa_a_formatacao_do_numero(self):
        """O separador decimal salvo é preservado; só a unidade é acrescentada."""
        self.assertEqual(formatar_dureza_com_unidade('99,9'), '99,9 HRC')
        self.assertEqual(formatar_dureza_com_unidade('153,5'), '153,5 HB')

    def test_valor_que_ja_traz_unidade_nao_duplica(self):
        self.assertEqual(formatar_dureza_com_unidade('33 HRC'), '33 HRC')
        self.assertEqual(formatar_dureza_com_unidade('153 HB'), '153 HB')

    def test_texto_nao_numerico_passa_como_esta(self):
        self.assertEqual(formatar_dureza_com_unidade('não medido'), 'não medido')
        self.assertEqual(formatar_dureza_com_unidade(True), '')
        self.assertEqual(formatar_dureza_com_unidade(Decimal('NaN')), 'NaN')
