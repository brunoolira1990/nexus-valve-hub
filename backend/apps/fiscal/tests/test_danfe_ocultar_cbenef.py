"""DANFE BFR — ocultar cBenef só na cópia efêmera (XML fiscal intacto)."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.nfe_cbenef_sp import ocultar_cbenef_para_danfe
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    XML_NFE_EXEMPLO_POC,
    gerar_danfe_bfr_de_xml_string,
    sanitizar_xml_para_bfr,
)
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text


def _xml_com_cbenef(codigo: str = 'SP020120', *, com_inf_ad: bool = True) -> str:
    xml = XML_NFE_EXEMPLO_POC.replace(
        '<xProd>Produto POC BrazilFiscalReport</xProd>',
        f'<xProd>Produto POC BrazilFiscalReport</xProd><cBenef>{codigo}</cBenef>',
        1,
    )
    if com_inf_ad:
        xml = xml.replace(
            '</prod>',
            '</prod><infAdProd>Pedido de compra: 55005050 - Item: 01</infAdProd>',
            1,
        )
    return xml


class DanfeOcultarCbenefEfemeroTests(SimpleTestCase):
    def test_xml_original_preservado_apos_sanitizar(self):
        original = _xml_com_cbenef('SP020120')
        guardado = original
        limpo = sanitizar_xml_para_bfr(original)
        self.assertIs(original, guardado)  # mesmo objeto string
        self.assertIn('<cBenef>SP020120</cBenef>', original)
        self.assertNotIn('cBenef', limpo)
        self.assertNotIn('SP020120', limpo)

    def test_namespace_nfe_removido_na_copia(self):
        xml = (
            '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
            '<det nItem="1"><prod>'
            '<xProd>Item NS</xProd>'
            '<cBenef>SP020120</cBenef>'
            '</prod></det></NFe>'
        )
        # Forma prefixada (alguns bindings)
        xml_pref = xml.replace(
            '<cBenef>SP020120</cBenef>',
            '<nfe:cBenef xmlns:nfe="http://www.portalfiscal.inf.br/nfe">SP020120</nfe:cBenef>',
        )
        out = ocultar_cbenef_para_danfe(xml_pref)
        self.assertNotIn('cBenef', out)
        self.assertIn('<xProd>Item NS</xProd>', out)

    def test_multiplos_itens_remove_todos_na_copia(self):
        xml = XML_NFE_EXEMPLO_POC.replace(
            '</det>',
            '</det>'
            '<det nItem="2"><prod><cProd>002</cProd><cEAN>SEM GTIN</cEAN>'
            '<xProd>Segundo Item</xProd><cBenef>SP111111</cBenef>'
            '<NCM>84818099</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>1.0000</qCom>'
            '<vUnCom>50.00</vUnCom><vProd>50.00</vProd><cEANTrib>SEM GTIN</cEANTrib>'
            '<uTrib>UN</uTrib><qTrib>1.0000</qTrib><vUnTrib>50.00</vUnTrib><indTot>1</indTot>'
            '</prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST>'
            '<modBC>3</modBC><vBC>50.00</vBC><pICMS>18.00</pICMS><vICMS>9.00</vICMS>'
            '</ICMS00></ICMS></imposto></det>',
            1,
        )
        xml = xml.replace(
            '<xProd>Produto POC BrazilFiscalReport</xProd>',
            '<xProd>Produto POC BrazilFiscalReport</xProd><cBenef>SP020120</cBenef>',
            1,
        )
        self.assertEqual(xml.count('<cBenef>'), 2)
        limpo = sanitizar_xml_para_bfr(xml)
        self.assertEqual(limpo.count('<cBenef>'), 0)
        self.assertIn('SP020120', xml)
        self.assertIn('SP111111', xml)
        self.assertNotIn('SP020120', limpo)
        self.assertNotIn('SP111111', limpo)

    def test_danfe_sem_cbenef_texto_com_xprod_e_infadprod(self):
        xml = _xml_com_cbenef('SP020120')
        pdf = gerar_danfe_bfr_de_xml_string(xml)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertNotIn('CBENEF', texto)
        self.assertNotIn('SP020120', texto)
        self.assertIn('PRODUTOPOCBRAZILFISCALREPORT', texto)
        self.assertIn('PEDIDODECOMPRA', texto.replace(' ', ''))
        # Totais do POC intactos no PDF
        self.assertIn('100,00', pdf_text(pdf) + texto)

    def test_xml_sem_cbenef_gera_danfe(self):
        pdf = gerar_danfe_bfr_de_xml_string(XML_NFE_EXEMPLO_POC)
        self.assertTrue(pdf.startswith(b'%PDF'))
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('PRODUTOPOCBRAZILFISCALREPORT', texto)

    def test_reimpressao_nao_altera_xml_autorizado_armazenado(self):
        """Simula XML autorizado em memória: sanitizar não reescreve a fonte."""
        xml_autorizado = _xml_com_cbenef('SP020120')
        armazenamento = {'xml': xml_autorizado}
        # Reimpressão: lê do armazenamento, sanitiza só para BFR
        fonte = armazenamento['xml']
        _ = gerar_danfe_bfr_de_xml_string(fonte)
        self.assertIn('<cBenef>SP020120</cBenef>', armazenamento['xml'])
        self.assertEqual(armazenamento['xml'], xml_autorizado)
