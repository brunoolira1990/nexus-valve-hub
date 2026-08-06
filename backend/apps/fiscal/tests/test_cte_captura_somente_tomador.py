"""Captura SEFAZ de CT-e — elegibilidade só quando a empresa é tomadora."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.dfe_recebidos.captura_sefaz import _cte_elegivel_captura

NS = 'http://www.portalfiscal.inf.br/cte'
CNPJ_NEXUS = '03999102000150'
CNPJ_TOMADOR = '79925442000280'
CNPJ_TRANSP = '50593947000121'
CHAVE = '35240750593947000121570010000000011000000011'


def _cte_xml(*, tomador_cnpj: str, dest_cnpj: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="{NS}" versao="4.00">
  <CTe>
    <infCte Id="CTe{CHAVE}" versao="4.00">
      <ide>
        <cUF>35</cUF><mod>57</mod><serie>1</serie><nCT>1</nCT>
        <cCT>00000011</cCT><cDV>1</cDV>
        <dhEmi>2026-07-31T22:13:00-03:00</dhEmi>
        <tpAmb>1</tpAmb><CFOP>5353</CFOP>
        <toma3><toma>0</toma></toma3>
      </ide>
      <emit><CNPJ>{CNPJ_TRANSP}</CNPJ><xNome>Transp</xNome></emit>
      <rem><CNPJ>{tomador_cnpj}</CNPJ><xNome>Remetente Tomador</xNome></rem>
      <dest><CNPJ>{dest_cnpj}</CNPJ><xNome>Destinatario</xNome></dest>
      <receb><CNPJ>{dest_cnpj}</CNPJ><xNome>Recebedor</xNome></receb>
      <vPrest><vTPrest>100.00</vTPrest><vRec>100.00</vRec></vPrest>
    </infCte>
  </CTe>
  <protCTe>
    <infProt><chCTe>{CHAVE}</chCTe><cStat>100</cStat><nProt>1</nProt></infProt>
  </protCTe>
</cteProc>
""".encode()


class CteElegivelCapturaTomadorTests(SimpleTestCase):
    def test_aceita_quando_empresa_e_tomadora(self):
        # toma=0 → tomador = remetente
        xml = _cte_xml(tomador_cnpj=CNPJ_NEXUS, dest_cnpj=CNPJ_TOMADOR)
        ok, motivo = _cte_elegivel_captura(xml, CNPJ_NEXUS)
        self.assertTrue(ok, motivo)

    def test_rejeita_quando_empresa_so_destinataria(self):
        xml = _cte_xml(tomador_cnpj=CNPJ_TOMADOR, dest_cnpj=CNPJ_NEXUS)
        ok, motivo = _cte_elegivel_captura(xml, CNPJ_NEXUS)
        self.assertFalse(ok)
        self.assertIn('tomadora', motivo.lower())
