"""DACTE Nexus (ReportLab) a partir do XML de CT-e histórico."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from apps.fiscal.dacte_nexus import gerar_dacte_nexus_pdf, montar_dacte_data, _serie_nro_de_chave_nfe
from apps.fiscal.documento_recebido_pdf import DocumentoRecebidoPdfError, gerar_dacte_cte_historico

NS = 'http://www.portalfiscal.inf.br/cte'
CHAVE = '35240750593947000121570010000000011000000011'
CHAVE_NFE = '35260603999102000150550010000003651333675950'


def _cte_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="{NS}" versao="4.00">
  <CTe>
    <infCte Id="CTe{CHAVE}" versao="4.00">
      <ide>
        <cUF>35</cUF><mod>57</mod><serie>1</serie><nCT>123</nCT>
        <cCT>00000011</cCT><cDV>1</cDV>
        <dhEmi>2026-07-31T22:13:00-03:00</dhEmi>
        <tpAmb>1</tpAmb><tpCTe>0</tpCTe><tpServ>0</tpServ>
        <CFOP>5353</CFOP><natOp>PRESTACAO DE SERVICO</natOp>
        <modal>01</modal>
        <xMunIni>SAO PAULO</xMunIni><UFIni>SP</UFIni>
        <xMunFim>RIO DE JANEIRO</xMunFim><UFFim>RJ</UFFim>
        <toma3><toma>0</toma></toma3>
      </ide>
      <emit>
        <CNPJ>50593947000121</CNPJ><IE>123</IE>
        <xNome>TRANSPORTE TESTE LTDA</xNome>
        <enderEmit>
          <xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro>
          <cMun>3550308</cMun><xMun>SAO PAULO</xMun><CEP>01001000</CEP><UF>SP</UF>
          <fone>1133334444</fone>
        </enderEmit>
      </emit>
      <rem>
        <CNPJ>03999102000150</CNPJ><IE>1</IE>
        <xNome>NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA</xNome>
        <enderReme>
          <xLgr>AV PAULISTA</xLgr><nro>100</nro><xBairro>BELA VISTA</xBairro>
          <cMun>3550308</cMun><xMun>SAO PAULO</xMun><CEP>01310100</CEP><UF>SP</UF>
        </enderReme>
      </rem>
      <dest>
        <CNPJ>02709449000168</CNPJ><xNome>CLIENTE DESTINO SA</xNome>
        <enderDest>
          <xLgr>RUA B</xLgr><nro>20</nro><xBairro>CENTRO</xBairro>
          <cMun>3304557</cMun><xMun>RIO DE JANEIRO</xMun><CEP>20040020</CEP><UF>RJ</UF>
        </enderDest>
      </dest>
      <vPrest>
        <vTPrest>100.00</vTPrest><vRec>100.00</vRec>
        <Comp><xNome>FRETE PESO</xNome><vComp>80.00</vComp></Comp>
        <Comp><xNome>PEDAGIO</xNome><vComp>20.00</vComp></Comp>
      </vPrest>
      <imp>
        <ICMS><ICMS00><CST>00</CST><vBC>100.00</vBC><pICMS>12.00</pICMS><vICMS>12.00</vICMS></ICMS00></ICMS>
      </imp>
      <infCTeNorm>
        <infCarga><proPred>DIVERSOS</proPred></infCarga>
        <infDoc><infNFe><chave>{CHAVE_NFE}</chave></infNFe></infDoc>
        <infModal versaoModal="4.00"><rodo><RNTRC>12345678</RNTRC></rodo></infModal>
      </infCTeNorm>
      <compl><xObs>Observacao de teste do DACTE Nexus.</xObs></compl>
    </infCte>
    <infCTeSupl><qrCodCTe>https://nfe.fazenda.sp.gov.br/CTeConsulta/qrCode?chCTe={CHAVE}&amp;tpAmb=1</qrCodCTe></infCTeSupl>
  </CTe>
  <protCTe>
    <infProt>
      <chCTe>{CHAVE}</chCTe><cStat>100</cStat><nProt>135240000000001</nProt>
      <dhRecbto>2026-07-31T22:20:00-03:00</dhRecbto>
    </infProt>
  </protCTe>
</cteProc>
"""


class SerieNroChaveTests(SimpleTestCase):
    def test_extrai_serie_numero(self):
        self.assertEqual(_serie_nro_de_chave_nfe(CHAVE_NFE), '001/000000365')


class DacteNexusMontagemTests(TestCase):
    def test_monta_dados_e_gera_pdf(self):
        xml = _cte_xml()
        data = montar_dacte_data(xml)
        self.assertEqual(data.chave, CHAVE)
        self.assertEqual(data.numero, '123')
        self.assertEqual(data.toma_label, 'REMETENTE')
        self.assertIn('TRANSPORTE TESTE', data.emit.get('xNome', ''))
        self.assertEqual(len(data.componentes), 2)
        self.assertEqual(data.chaves_nfe, [CHAVE_NFE])
        self.assertTrue(data.qr_url.startswith('https://'))

        pdf = gerar_dacte_nexus_pdf(xml)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 2000)

    def test_endpoint_helper_usa_gerador_nexus(self):
        pdf = gerar_dacte_cte_historico(_cte_xml())
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_xml_vazio_rejeita(self):
        with self.assertRaises(DocumentoRecebidoPdfError):
            gerar_dacte_cte_historico('   ')
