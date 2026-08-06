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


class PatchDrawHeaderEmitenteTests(SimpleTestCase):
    def test_endereco_fica_abaixo_do_nome_quebrado(self):
        from apps.fiscal.dacte_bfr_emit import patch_draw_header_emitente

        class FakePdf:
            def __init__(self):
                self.emit_name = 'RODOMAC DE MACAE RODOVIARIO LTDA'
                self._y = 10.0
                self.calls: list[tuple] = []

            def get_y(self):
                return self._y

            def set_xy(self, x=0, y=0):
                self.calls.append(('xy', x, y))
                self._y = y

            def multi_cell(self, w, h=None, text='', border=0, align='J', **kwargs):
                if 'text' in kwargs:
                    text = kwargs['text']
                self.calls.append(('cell', text))
                # simula quebra de nome em 2 linhas
                if text == self.emit_name:
                    self._y += 10
                else:
                    self._y += 3 * max(1, text.count('\n') + 1)

        pdf = FakePdf()

        def fake_header(d):
            d.set_xy(x=1, y=10)
            d.multi_cell(w=50, h=5, text=d.emit_name, border=0, align='C')
            d.set_xy(x=1, y=16)  # BFR: y_text+6 sobrepõe a 2ª linha do nome
            d.multi_cell(
                w=60,
                h=3,
                text='CNPJ: 36.578.458/0003-31 IE: 113786676117\nRUA A, 1',
                border=0,
                align='C',
            )

        patch_draw_header_emitente(pdf, fake_header)
        xy_calls = [c for c in pdf.calls if c[0] == 'xy']
        cell_calls = [c for c in pdf.calls if c[0] == 'cell']
        # 2º set_xy (endereço) deve usar get_y() pós-nome (~20.5), não 16
        self.assertGreater(xy_calls[1][2], 16)
        addr = cell_calls[1][1]
        self.assertIn('CNPJ: 36.578.458/0003-31\nIE: ', addr)
        self.assertNotIn('CNPJ: 36.578.458/0003-31 IE: ', addr)


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
        # DacteNexus wraps the class; FakeDacte must work as base for subclassing.
        # Bypass subclass path by patching _classe_dacte_nexus to identity.
        with patch('apps.fiscal.documento_recebido_pdf._classe_dacte_nexus', side_effect=lambda C: C):
            pdf = gerar_dacte_cte_historico(_cte_proc_minimo())
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(len(xml_passado), 1)
        self.assertEqual(ET.fromstring(xml_passado[0]).tag.split('}')[-1], 'cteProc')
