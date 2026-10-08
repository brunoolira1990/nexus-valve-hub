"""Teste — cBenef: códigos reais vs. marcadores (rejeição SEFAZ cStat 946)."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.nfe_cbenef_sp import (
    CBENEF_SEM_CODIGO_LITERAL,
    MSG_CBENEF_MARCADOR_INVALIDO,
    MSG_CBENEF_SP_CST20_REDUCAO,
    codigo_beneficio_icms_para_snapshot,
    codigo_beneficio_icms_para_xml,
    codigo_beneficio_icms_preenchido,
    eh_marcador_cbenef_nao_fiscal,
    item_exige_cbenef_sp_cst20_reducao,
    normalizar_codigo_beneficio_icms,
    ocultar_cbenef_para_danfe,
    ocultar_sem_cbenef_para_danfe,
    pendencia_cbenef_marcador_item,
    pendencia_cbenef_sp_item,
)
from apps.fiscal.nfe_saida_xml_nfelib import _build_det


class NFeCbenefSpTests(SimpleTestCase):
    def test_normaliza_sem_cbenef_legado(self):
        self.assertEqual(normalizar_codigo_beneficio_icms('sem cbenef'), CBENEF_SEM_CODIGO_LITERAL)
        self.assertEqual(normalizar_codigo_beneficio_icms('SEM CBENEF'), CBENEF_SEM_CODIGO_LITERAL)

    def test_marcador_nao_e_codigo_preenchido(self):
        self.assertTrue(eh_marcador_cbenef_nao_fiscal(CBENEF_SEM_CODIGO_LITERAL))
        self.assertTrue(eh_marcador_cbenef_nao_fiscal('SEM BENEFICIO'))
        self.assertFalse(codigo_beneficio_icms_preenchido(CBENEF_SEM_CODIGO_LITERAL))
        self.assertIsNone(codigo_beneficio_icms_para_xml(CBENEF_SEM_CODIGO_LITERAL))
        self.assertEqual(codigo_beneficio_icms_para_snapshot(CBENEF_SEM_CODIGO_LITERAL), '')

    def test_sp020120_serializavel(self):
        self.assertEqual(codigo_beneficio_icms_para_xml('SP020120'), 'SP020120')
        self.assertTrue(codigo_beneficio_icms_preenchido('SP020120'))
        self.assertEqual(codigo_beneficio_icms_para_snapshot('SP020120'), 'SP020120')

    def test_pendencia_sp_cst20_sem_codigo(self):
        snap = {'cst_icms': '20', 'reducao_bc_icms': '51.1100'}
        msg = pendencia_cbenef_sp_item(snap, uf_emitente='SP', rotulo_item='Item 1')
        self.assertIn(MSG_CBENEF_SP_CST20_REDUCAO, msg or '')

    def test_sem_cbenef_nao_fecha_pendencia_cst20(self):
        """cStat 946 — marcador NÃO satisfaz exigência de CST 20 + redução."""
        snap = {
            'cst_icms': '20',
            'reducao_bc_icms': '51.1100',
            'codigo_beneficio_icms': CBENEF_SEM_CODIGO_LITERAL,
        }
        self.assertIsNotNone(pendencia_cbenef_marcador_item(snap, rotulo_item='Item'))
        self.assertIn(MSG_CBENEF_SP_CST20_REDUCAO, pendencia_cbenef_sp_item(snap, uf_emitente='SP') or '')

    def test_sp020120_fecha_pendencia_artigo12(self):
        snap = {
            'cst_icms': '20',
            'reducao_bc_icms': '51.1100',
            'codigo_beneficio_icms': 'SP020120',
        }
        self.assertIsNone(pendencia_cbenef_marcador_item(snap))
        self.assertIsNone(pendencia_cbenef_sp_item(snap, uf_emitente='SP'))

    def test_nao_exige_fora_sp(self):
        snap = {'cst_icms': '20', 'reducao_bc_icms': '51.1100'}
        self.assertFalse(item_exige_cbenef_sp_cst20_reducao(snap, uf_emitente='RJ'))

    def test_ocultar_cbenef_para_danfe_remove_todos(self):
        xml = (
            '<prod><cBenef>SEM CBENEF</cBenef><xProd>Item</xProd>'
            '<cBenef>SP020120</cBenef>'
            '<nfe:cBenef xmlns:nfe="http://www.portalfiscal.inf.br/nfe">SP999999</nfe:cBenef>'
            '</prod>'
        )
        original = xml
        out = ocultar_cbenef_para_danfe(xml)
        self.assertEqual(xml, original)  # string imutável / cópia
        self.assertNotIn('cBenef', out)
        self.assertNotIn('SP020120', out)
        self.assertNotIn('SEM CBENEF', out)
        self.assertIn('<xProd>Item</xProd>', out)

    def test_ocultar_sem_cbenef_alias_remove_codigo_real(self):
        xml = '<prod><cBenef>SP123456</cBenef></prod>'
        self.assertNotIn('cBenef', ocultar_sem_cbenef_para_danfe(xml))

    def test_marcador_bloqueia_emissao_mensagem(self):
        snap = {'codigo_beneficio_icms': 'SEM BENEFICIO'}
        msg = pendencia_cbenef_marcador_item(snap, rotulo_item='Item 2')
        self.assertIn(MSG_CBENEF_MARCADOR_INVALIDO, msg or '')


class NFeCbenefXml946Tests(SimpleTestCase):
    """Rejeição 946: SEM CBENEF no XML; SP020120 deve ir para cBenef."""

    def _linha(self, codigo_beneficio: str):
        snap = {
            'origem_mercadoria': '0',
            'cst_icms': '20',
            'modalidade_bc_icms': '3',
            'reducao_bc_icms': '51.1100',
            'base_icms': '2444.50',
            'aliquota_icms': '18.00',
            'valor_icms': '440.01',
            'codigo_beneficio_icms': codigo_beneficio,
        }
        return {
            'n_item': '1',
            'c_prod': '2043.05',
            'x_prod': 'Item Artigo 12',
            'ncm': '84818095',
            'cfop': '5102',
            'u_com': 'PC',
            'q_com': '10',
            'v_un_com': '500.00',
            'v_prod': '5000.00',
            'snapshot_fiscal': snap,
        }

    def test_sp020120_gera_cbenef_no_xml(self):
        det = _build_det(self._linha('SP020120'))
        self.assertEqual(det.prod.cBenef, 'SP020120')

    def test_sem_cbenef_omite_tag(self):
        det = _build_det(self._linha(CBENEF_SEM_CODIGO_LITERAL))
        self.assertIsNone(det.prod.cBenef)

    def test_vazio_omite_tag(self):
        det = _build_det(self._linha(''))
        self.assertIsNone(det.prod.cBenef)

    def test_preview_transmissao_mesmo_valor_sp020120(self):
        """Preview (_build_det) e XML de transmissão usam o mesmo helper."""
        from apps.fiscal.nfe_cbenef_sp import codigo_beneficio_icms_para_xml

        self.assertEqual(codigo_beneficio_icms_para_xml('SP020120'), 'SP020120')
        det = _build_det(self._linha('SP020120'))
        self.assertEqual(det.prod.cBenef, codigo_beneficio_icms_para_xml('SP020120'))
