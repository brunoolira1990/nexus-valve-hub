"""DACTE a partir do XML de CT-e histórico — normalização para BrazilFiscalReport."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.fiscal.documento_recebido_pdf import (
    DocumentoRecebidoPdfError,
    _normalizar_xml_cte_para_dacte,
    gerar_dacte_cte_historico,
)

NS = 'http://www.portalfiscal.inf.br/cte'


def _cte_proc_minimo() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="{NS}" versao="4.00">
  <CTe>
    <infCte Id="CTe35240112345678000123570010000000011000000011" versao="4.00">
      <ide><cUF>35</cUF><mod>57</mod><nCT>1</nCT></ide>
      <emit><CNPJ>12345678000123</CNPJ><xNome>Transp Teste</xNome></emit>
    </infCte>
  </CTe>
  <protCTe>
    <infProt><nProt>135240000000001</nProt><cStat>100</cStat></infProt>
  </protCTe>
</cteProc>
"""


class NormalizarXmlCteParaDacteTests(SimpleTestCase):
    def test_cte_proc_permanece_cte_proc(self):
        out = _normalizar_xml_cte_para_dacte(_cte_proc_minimo())
        root = ET.fromstring(out)
        self.assertEqual(root.tag.split('}')[-1], 'cteProc')
        self.assertIsNotNone(
            root.find(f'.//{{{NS}}}infCte'),
            'infCte deve permanecer acessível como descendente',
        )

    def test_cte_raiz_permanece_cte(self):
        xml = f'<CTe xmlns="{NS}"><infCte Id="CTe1"><ide/></infCte></CTe>'
        out = _normalizar_xml_cte_para_dacte(xml)
        root = ET.fromstring(out)
        self.assertEqual(root.tag.split('}')[-1], 'CTe')

    def test_inf_cte_solto_e_embrulhado_em_cte(self):
        xml = f'<infCte xmlns="{NS}" Id="CTe1"><ide/></infCte>'
        out = _normalizar_xml_cte_para_dacte(xml)
        root = ET.fromstring(out)
        self.assertEqual(root.tag.split('}')[-1], 'CTe')
        self.assertIsNotNone(root.find(f'.//{{{NS}}}infCte'))

    def test_xml_sem_inf_cte_rejeita(self):
        with self.assertRaises(DocumentoRecebidoPdfError):
            _normalizar_xml_cte_para_dacte(f'<cteProc xmlns="{NS}"><foo/></cteProc>')


class GerarDacteCteHistoricoTests(SimpleTestCase):
    @patch('apps.fiscal.documento_recebido_pdf._importar_dacte')
    def test_gera_pdf_com_cte_proc_sem_reduzir_a_inf_cte(self, mock_import):
        xml_passado: list[str] = []

        class FakeDacte:
            def __init__(self, xml, config=None):
                xml_passado.append(xml)
                root = ET.fromstring(xml)
                # Replica a expectativa do BFR: infCte como descendente, não como raiz.
                inf = root.find(f'.//{{{NS}}}infCte')
                if inf is None:
                    raise AttributeError("'NoneType' object has no attribute 'attrib'")
                self._ok = True

            def output(self, buffer: BytesIO):
                buffer.write(b'%PDF-1.4 fake-dacte')

        mock_import.return_value = (FakeDacte, MagicMock())
        pdf = gerar_dacte_cte_historico(_cte_proc_minimo())
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(len(xml_passado), 1)
        self.assertEqual(ET.fromstring(xml_passado[0]).tag.split('}')[-1], 'cteProc')
