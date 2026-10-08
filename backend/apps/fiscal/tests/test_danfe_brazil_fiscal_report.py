"""POC NF-e 3.5.4.6 — BrazilFiscalReport para DANFE (isolado, sem efeitos fiscais)."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.fiscal.danfe_render import DanfeBfrRenderError, RENDER_ENGINES_OFICIAIS, render_danfe_conferencia_pdf
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    XML_NFE_EXEMPLO_POC,
    DanfeBfrError,
    brazil_fiscal_report_disponivel,
    gerar_danfe_bfr_de_xml_bytes,
    gerar_danfe_bfr_de_xml_string,
    gerar_danfe_bfr_debug_file,
    sanitizar_xml_para_bfr,
)
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _regra() -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm='84818200',
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'Venda SP',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
        },
    )
    return regra


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DanfeBrazilFiscalReportPocTests(TestCase):
    def test_biblioteca_importa(self):
        self.assertTrue(brazil_fiscal_report_disponivel())

    def test_gera_pdf_xml_exemplo(self):
        pdf = gerar_danfe_bfr_de_xml_string(XML_NFE_EXEMPLO_POC)
        self.assertTrue(pdf.startswith(b'%PDF'))
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('DANFE', texto)
        self.assertIn('EMITENTETESTELTDA', texto)
        # tpAmb=2: BFR substitui razão social do destinatário por aviso de homologação.
        self.assertTrue(
            'DESTINARIOTESTE' in texto or 'HOMOLOGACAO' in texto,
            msg='destinatário ou aviso homologação esperado',
        )
        self.assertIn('PRODUTOPOCBRAZILFISCALREPORT', texto)

    def test_pdf_bytes_helper(self):
        pdf = gerar_danfe_bfr_de_xml_bytes(XML_NFE_EXEMPLO_POC.encode('utf-8'))
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_xml_invalido_erro_amigavel(self):
        with self.assertRaises(DanfeBfrError):
            gerar_danfe_bfr_de_xml_string('<html>nao e nfe</html>')

    def test_debug_file_salva_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = gerar_danfe_bfr_debug_file(XML_NFE_EXEMPLO_POC, Path(tmp) / 'danfe.pdf')
            data = Path(path).read_bytes()
            self.assertTrue(data.startswith(b'%PDF'))

    def test_sanitiza_xml_previa_comentarios(self):
        xml = (
            '<?xml version="1.0"?>\n<!-- comentario -->\n'
            '<?xml version="1.0"?><NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
            '<infNFe Id="NFePREVIEW1" versao="4.00"><ide><nNF>1</nNF><tpAmb>2</tpAmb></ide>'
            '<emit><CNPJ>12345678000190</CNPJ><xNome>E</xNome><IE>1</IE><CRT>3</CRT>'
            '<enderEmit><xLgr>R</xLgr><nro>1</nro><xMun>M</xMun><UF>SP</UF></enderEmit></emit>'
            '<dest><CNPJ>98765432000110</CNPJ><xNome>D</xNome><indIEDest>9</indIEDest>'
            '<enderDest><xLgr>R</xLgr><nro>1</nro><xMun>M</xMun><UF>SP</UF></enderDest></dest>'
            '<det nItem="1"><prod><cProd>1</cProd><xProd>P</xProd><NCM>1</NCM><CFOP>5102</CFOP>'
            '<uCom>UN</uCom><qCom>1</qCom><vUnCom>1</vUnCom><vProd>1</vProd>'
            '<uTrib>UN</uTrib><qTrib>1</qTrib><vUnTrib>1</vUnTrib><indTot>1</indTot></prod>'
            '<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST></ICMS00></ICMS></imposto></det>'
            '<total><ICMSTot><vProd>1</vProd><vNF>1</vNF></ICMSTot></total>'
            '<transp><modFrete>9</modFrete></transp></infNFe></NFe>'
        )
        limpo = sanitizar_xml_para_bfr(xml)
        self.assertNotIn('<!--', limpo)
        pdf = gerar_danfe_bfr_de_xml_string(limpo)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_danfe_oculta_qualquer_cbenef_mantem_pedido_e_xprod(self):
        """cBenef permanece no XML fiscal; BFR não exibe cBenef: no PDF."""
        xml = XML_NFE_EXEMPLO_POC.replace(
            '<xProd>Produto POC BrazilFiscalReport</xProd>',
            '<xProd>Produto POC BrazilFiscalReport</xProd><cBenef>SP020120</cBenef>',
            1,
        ).replace(
            '</prod>',
            '</prod><infAdProd>Pedido de compra: 55005050 - Item: 01</infAdProd>',
            1,
        )
        original = xml
        self.assertIn('<cBenef>SP020120</cBenef>', original)

        limpo = sanitizar_xml_para_bfr(xml)
        self.assertEqual(xml, original)  # original preservado
        self.assertIn('<cBenef>SP020120</cBenef>', xml)
        self.assertNotIn('cBenef', limpo)
        self.assertNotIn('SP020120', limpo)
        self.assertIn('Produto POC BrazilFiscalReport', limpo)
        self.assertIn('Pedido de compra: 55005050', limpo)

        pdf = gerar_danfe_bfr_de_xml_string(xml)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertNotIn('CBENEF', texto)
        self.assertNotIn('SP020120', texto)
        self.assertIn('PRODUTOPOCBRAZILFISCALREPORT', texto)
        self.assertIn('PEDIDODECOMPRA', texto.replace(' ', ''))

        # Marcador legado também some do PDF; XML de entrada intacto.
        xml_sem = xml.replace('<cBenef>SP020120</cBenef>', '<cBenef>SEM CBENEF</cBenef>', 1)
        pdf_sem = gerar_danfe_bfr_de_xml_string(xml_sem)
        texto_sem = compact_pdf_text(pdf_text(pdf_sem))
        self.assertNotIn('SEM CBENEF', texto_sem)
        self.assertNotIn('CBENEF:SEM', texto_sem.replace(' ', ''))

    @mock.patch(
        'apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report.gerar_danfe_bfr_de_nfe_saida_preview',
    )
    def test_falha_bfr_retorna_erro_sem_fallback_html(self, mock_bfr):
        mock_bfr.side_effect = DanfeBfrError('falha simulada')
        user = get_user_model().objects.create_user('bfr1', 'bfr1@test.com', 'x')
        client = APIClient()
        client.force_authenticate(user)
        _regra()
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00', 'aliquota_icms': '18'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])

        res = client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')

        self.assertEqual(res.status_code, 503)
        self.assertIn('BFR', res.json().get('detail', ''))

    def test_render_oficial_bfr_apenas(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        _regra()
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
            'aliquota_icms': '18',
            'cst_pis': '01',
            'aliquota_pis': '1.65',
            'cst_cofins': '01',
            'aliquota_cofins': '7.6',
        }
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        emp = nf.pedido_venda.empresa_emitente
        emp.ie = '123456789012'
        emp.save(update_fields=['ie'])
        pdf, meta = render_danfe_conferencia_pdf({'nfe_saida_id': nf.pk}, nfe_saida_id=nf.pk)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(meta.get('render_engine'), RENDER_ENGINES_OFICIAIS)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('DANFE', texto)

    @override_settings(DANFE_ALLOW_HTML_FALLBACK=False)
    def test_fallback_html_bloqueado_levanta_erro(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        _regra()
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00', 'aliquota_icms': '18'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        with mock.patch(
            'apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report.gerar_danfe_bfr_de_nfe_saida_preview',
            side_effect=DanfeBfrError('simulado'),
        ):
            with self.assertRaises(DanfeBfrRenderError):
                render_danfe_conferencia_pdf({'nfe_saida_id': nf.pk}, nfe_saida_id=nf.pk)

    def test_gerar_pdf_nao_altera_status_nem_eventos(self):
        _regra()
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00', 'aliquota_icms': '18'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        status_antes = nf.status
        eventos_antes = NFeSaidaEvento.objects.count()
        pdf = gerar_danfe_bfr_de_xml_string(XML_NFE_EXEMPLO_POC)
        self.assertTrue(pdf.startswith(b'%PDF'))
        nf.refresh_from_db()
        self.assertEqual(nf.status, status_antes)
        self.assertEqual(NFeSaidaEvento.objects.count(), eventos_antes)

