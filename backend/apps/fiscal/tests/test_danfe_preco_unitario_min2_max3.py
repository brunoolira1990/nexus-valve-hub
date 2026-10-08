"""DANFE BFR — preço unitário min 2 / max 3 casas (override DanfeNexus)."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    gerar_danfe_bfr_de_xml_string,
    sanitizar_xml_para_bfr,
)
from apps.fiscal.nfe_integracao.danfe_preco_unitario_format import format_preco_unitario_danfe
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text


def _xml_sintetico(*, v_un: str, v_prod: str = '4512.50', q_com: str = '4.0000') -> str:
    """XML sintético mínimo; vUnCom e vUnTrib iguais ao valor informado."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
        '<NFe><infNFe Id="NFe35200100000000000000550010000000011000000010" versao="4.00">'
        '<ide><cUF>35</cUF><cNF>00000001</cNF><natOp>Venda</natOp><mod>55</mod>'
        '<serie>1</serie><nNF>1</nNF><dhEmi>2026-01-15T10:00:00-03:00</dhEmi>'
        '<tpNF>1</tpNF><idDest>1</idDest><cMunFG>3550308</cMunFG><tpImp>1</tpImp>'
        '<tpEmis>1</tpEmis><cDV>0</cDV><tpAmb>2</tpAmb><finNFe>1</finNFe>'
        '<indFinal>1</indFinal><indPres>1</indPres><procEmi>0</procEmi><verProc>Nexus</verProc></ide>'
        '<emit><CNPJ>12345678000199</CNPJ><xNome>Emit Teste</xNome>'
        '<enderEmit><xLgr>Rua A</xLgr><nro>1</nro><xBairro>Centro</xBairro>'
        '<cMun>3550308</cMun><xMun>Sao Paulo</xMun><UF>SP</UF><CEP>01001000</CEP>'
        '<cPais>1058</cPais><xPais>Brasil</xPais></enderEmit>'
        '<IE>123456789012</IE><CRT>3</CRT></emit>'
        '<dest><CNPJ>98765432000111</CNPJ><xNome>Dest Teste</xNome>'
        '<enderDest><xLgr>Rua B</xLgr><nro>2</nro><xBairro>Centro</xBairro>'
        '<cMun>3304557</cMun><xMun>Rio de Janeiro</xMun><UF>RJ</UF><CEP>20040020</CEP>'
        '<cPais>1058</cPais><xPais>Brasil</xPais></enderDest>'
        '<indIEDest>9</indIEDest></dest>'
        '<det nItem="1"><prod><cProd>001</cProd><cEAN>SEM GTIN</cEAN>'
        '<xProd>Item sintetico</xProd><NCM>84818099</NCM><CFOP>5102</CFOP>'
        f'<uCom>UN</uCom><qCom>{q_com}</qCom><vUnCom>{v_un}</vUnCom><vProd>{v_prod}</vProd>'
        f'<cEANTrib>SEM GTIN</cEANTrib><uTrib>UN</uTrib><qTrib>{q_com}</qTrib>'
        f'<vUnTrib>{v_un}</vUnTrib><indTot>1</indTot></prod>'
        '<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC>'
        f'<vBC>{v_prod}</vBC><pICMS>18.00</pICMS><vICMS>812.25</vICMS></ICMS00></ICMS>'
        f'<PIS><PISAliq><CST>01</CST><vBC>{v_prod}</vBC><pPIS>1.65</pPIS><vPIS>74.46</vPIS></PISAliq></PIS>'
        f'<COFINS><COFINSAliq><CST>01</CST><vBC>{v_prod}</vBC><pCOFINS>7.60</pCOFINS>'
        '<vCOFINS>342.95</vCOFINS></COFINSAliq></COFINS></imposto></det>'
        f'<total><ICMSTot><vBC>{v_prod}</vBC><vICMS>812.25</vICMS><vICMSDeson>0.00</vICMSDeson>'
        '<vFCP>0.00</vFCP><vBCST>0.00</vBCST><vST>0.00</vST><vFCPST>0.00</vFCPST>'
        f'<vFCPSTRet>0.00</vFCPSTRet><vProd>{v_prod}</vProd><vFrete>0.00</vFrete>'
        '<vSeg>0.00</vSeg><vDesc>0.00</vDesc><vII>0.00</vII><vIPI>0.00</vIPI>'
        f'<vIPIDevol>0.00</vIPIDevol><vPIS>74.46</vPIS><vCOFINS>342.95</vCOFINS>'
        f'<vOutro>0.00</vOutro><vNF>{v_prod}</vNF></ICMSTot></total>'
        '<transp><modFrete>9</modFrete></transp>'
        f'<pag><detPag><tPag>01</tPag><vPag>{v_prod}</vPag></detPag></pag>'
        '</infNFe></NFe></nfeProc>'
    )


class FormatPrecoUnitarioDanfeHelperTests(SimpleTestCase):
    def test_casos_obrigatorios_min2_max3(self):
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128')), '1.128,00')
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128.1')), '1.128,10')
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128.12')), '1.128,12')
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128.120')), '1.128,12')
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128.125')), '1.128,125')

    def test_quatro_casas_round_half_up_para_tres(self):
        # 1128.1234 → 1128.123; 1128.1235 → 1128.124
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128.1234')), '1.128,123')
        self.assertEqual(format_preco_unitario_danfe(Decimal('1128.1235')), '1.128,124')

    def test_aceita_string_sem_float(self):
        self.assertEqual(format_preco_unitario_danfe('1128.125'), '1.128,125')
        self.assertEqual(format_preco_unitario_danfe('10.1'), '10,10')


class DanfePrecoUnitarioMin2Max3PdfTests(SimpleTestCase):
    """Asserts no texto compacto do PDF (pypdf remove espaços; compact remove milhar '.')."""

    def _pdf_compact(self, v_un: str, **kwargs) -> tuple[str, str, bytes]:
        xml = _xml_sintetico(v_un=v_un, **kwargs)
        xml_antes = xml
        pdf = gerar_danfe_bfr_de_xml_string(sanitizar_xml_para_bfr(xml))
        self.assertTrue(pdf.startswith(b'%PDF'))
        # XML de entrada permanece com o valor original (sanitizar não reescreve números).
        self.assertIn(f'<vUnCom>{v_un}</vUnCom>', xml_antes)
        self.assertIn(f'<vUnTrib>{v_un}</vUnTrib>', xml_antes)
        return compact_pdf_text(pdf_text(pdf)), xml_antes, pdf

    def test_inteiro_duas_casas_sem_terceiro_zero(self):
        texto, xml, _ = self._pdf_compact('1128', v_prod='4512.00')
        self.assertIn('1128,00', texto)
        self.assertNotIn('1128,000', texto)
        self.assertIn('<vUnCom>1128</vUnCom>', xml)

    def test_uma_casa_vira_duas(self):
        texto, _, _ = self._pdf_compact('1128.1', v_prod='4512.40')
        self.assertIn('1128,10', texto)
        self.assertNotIn('1128,100', texto)

    def test_duas_casas_sem_terceiro_zero(self):
        texto, _, _ = self._pdf_compact('1128.12', v_prod='4512.48')
        self.assertIn('1128,12', texto)
        self.assertNotIn('1128,120', texto)

    def test_terceira_casa_significativa(self):
        texto, _, _ = self._pdf_compact('1128.125', v_prod='4512.50')
        self.assertIn('1128,125', texto)

    def test_quatro_casas_limitadas_visualmente_xml_intacto(self):
        xml = _xml_sintetico(v_un='1128.1234', v_prod='4512.49')
        self.assertIn('<vUnCom>1128.1234</vUnCom>', xml)
        self.assertIn('<vUnTrib>1128.1234</vUnTrib>', xml)
        limpo = sanitizar_xml_para_bfr(xml)
        self.assertIn('<vUnCom>1128.1234</vUnCom>', limpo)
        self.assertIn('<vUnTrib>1128.1234</vUnTrib>', limpo)
        texto = compact_pdf_text(pdf_text(gerar_danfe_bfr_de_xml_string(limpo)))
        # compact concatena colunas: 1128,123 + 4512 → "1128,1234512" (não confundir com 4ª casa).
        self.assertIn('1128,1234512', texto)
        self.assertNotRegex(texto, r'1128,1234(?!\d)')

    def test_vuntrib_mesma_regra(self):
        # vUnCom e vUnTrib iguais → uma coluna; regra min2/max3 vale para ambos.
        texto, xml, _ = self._pdf_compact('1128.125')
        self.assertIn('<vUnTrib>1128.125</vUnTrib>', xml)
        self.assertIn('1128,125', texto)

    def test_quantidades_vprod_impostos_totais_inalterados(self):
        texto, _, _ = self._pdf_compact('1128.125', v_prod='4512.50', q_com='4.0000')
        self.assertIn('4,0000', texto)
        self.assertIn('4512,50', texto)
        self.assertIn('812,25', texto)
        self.assertIn('74,46', texto)

    def test_reimpressao_deterministica(self):
        xml = sanitizar_xml_para_bfr(_xml_sintetico(v_un='1128.125'))
        pdf1 = gerar_danfe_bfr_de_xml_string(xml)
        pdf2 = gerar_danfe_bfr_de_xml_string(xml)
        self.assertEqual(pdf1, pdf2)
