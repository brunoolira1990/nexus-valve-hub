"""Teste pontual — cBenef SP / SEM CBENEF."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.nfe_cbenef_sp import (
    CBENEF_SEM_CODIGO_LITERAL,
    MSG_CBENEF_SP_CST20_REDUCAO,
    codigo_beneficio_icms_preenchido,
    item_exige_cbenef_sp_cst20_reducao,
    normalizar_codigo_beneficio_icms,
    ocultar_sem_cbenef_para_danfe,
    pendencia_cbenef_sp_item,
)


class NFeCbenefSpTests(SimpleTestCase):
    def test_normaliza_sem_cbenef(self):
        self.assertEqual(normalizar_codigo_beneficio_icms('sem cbenef'), CBENEF_SEM_CODIGO_LITERAL)
        self.assertEqual(normalizar_codigo_beneficio_icms('SEM CBENEF'), CBENEF_SEM_CODIGO_LITERAL)

    def test_sem_cbenef_e_preenchido(self):
        self.assertTrue(codigo_beneficio_icms_preenchido(CBENEF_SEM_CODIGO_LITERAL))

    def test_pendencia_sp_cst20_sem_codigo(self):
        snap = {'cst_icms': '20', 'reducao_bc_icms': '51.1100'}
        msg = pendencia_cbenef_sp_item(snap, uf_emitente='SP', rotulo_item='Item 1')
        self.assertIn(MSG_CBENEF_SP_CST20_REDUCAO, msg or '')

    def test_sem_pendencia_com_sem_cbenef(self):
        snap = {
            'cst_icms': '20',
            'reducao_bc_icms': '51.1100',
            'codigo_beneficio_icms': CBENEF_SEM_CODIGO_LITERAL,
        }
        self.assertIsNone(pendencia_cbenef_sp_item(snap, uf_emitente='SP'))

    def test_nao_exige_fora_sp(self):
        snap = {'cst_icms': '20', 'reducao_bc_icms': '51.1100'}
        self.assertFalse(item_exige_cbenef_sp_cst20_reducao(snap, uf_emitente='RJ'))

    def test_ocultar_sem_cbenef_apenas_literal(self):
        xml = (
            '<prod><cBenef>SEM CBENEF</cBenef><xProd>Item</xProd>'
            '<cBenef>SP123456</cBenef></prod>'
        )
        out = ocultar_sem_cbenef_para_danfe(xml)
        self.assertNotIn('SEM CBENEF', out)
        self.assertIn('<cBenef>SP123456</cBenef>', out)

    def test_ocultar_nao_altera_xml_sem_sem_cbenef(self):
        xml = '<prod><cBenef>SP123456</cBenef></prod>'
        self.assertEqual(ocultar_sem_cbenef_para_danfe(xml), xml)
