"""NF-e 4.0.1 — XML preliminar nfelib + DANFE BrazilFiscalReport."""

from __future__ import annotations

import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.danfe_render import gerar_danfe_bfr_oficial
from apps.fiscal.models import AtendimentoEstoque, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    brazil_fiscal_report_disponivel,
    gerar_danfe_bfr_nfe_preliminar,
)
from apps.fiscal.nfe_integracao.nfe_xml_preliminar import (
    gerar_resultado_xml_preliminar,
    gerar_xml_nfe_preliminar,
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


def _nf_pronta(*, ie_emit: str = '123456789012', ie_dest: str = '') -> NFeSaida:
    _regra()
    pedido, item = _pedido_item(qtd=Decimal('4'), preco=Decimal('100'))
    item.snapshot_fiscal = {
        'ncm': '84818200',
        'cfop': '5102',
        'cst_icms': '00',
        'aliquota_icms': '18',
        'valor_icms': '72',
        'base_icms': '400',
        'cst_pis': '01',
        'aliquota_pis': '1.65',
        'valor_pis': '6.6',
        'cst_cofins': '01',
        'aliquota_cofins': '7.6',
        'valor_cofins': '30.4',
    }
    item.save(update_fields=['snapshot_fiscal'])
    fat = _faturamento_pronto(pedido, item, qtd='4')
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    nf = NFeSaida.objects.select_related(
        'cliente',
        'pedido_venda__empresa_emitente',
    ).get(pk=r['nfe_saida_id'])
    emp = nf.pedido_venda.empresa_emitente
    emp.ie = ie_emit
    emp.save(update_fields=['ie'])
    cli = nf.cliente
    cli.ie = ie_dest
    cli.save(update_fields=['ie'])
    nf.informacoes_adicionais = 'Info compl preliminar 401'
    nf.save(update_fields=['informacoes_adicionais'])
    return nf


@override_settings(
    USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True,
    FISCAL_PERSISTIR_XML_PRELIMINAR=True,
)
class NFeSaida401BfrPreliminarTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe401bfr', 'nfe401bfr@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_xml_preliminar_gerado(self):
        self.assertTrue(nfelib_disponivel())
        nf = _nf_pronta()
        data = gerar_resultado_xml_preliminar(nf)
        self.assertFalse(data.get('bloqueado'))
        self.assertEqual(data.get('xml_format'), 'nfelib_4.00_preliminar')
        self.assertIn('portalfiscal.inf.br/nfe', data['xml'])

    def test_xml_preliminar_monta_pag_cobr_sem_erro(self):
        """Regressão: montar_tnfe_preliminar usava tot indefinido."""
        from apps.fiscal.nfe_integracao.nfe_chave_acesso import montar_chave_acesso_nfe
        from apps.fiscal.nfe_integracao.nfe_numero_fiscal_preliminar import resolver_numero_fiscal_preliminar
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import montar_tnfe_preliminar
        from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida

        nf = _nf_pronta()
        dados = gerar_dados_preview_nfe_saida(nf, incluir_validacao_emissao=False)
        numeracao = resolver_numero_fiscal_preliminar(nf)
        emit_cnpj = ''.join(c for c in str(dados['emitente'].get('cnpj', '')) if c.isdigit())
        chave = montar_chave_acesso_nfe(
            cuf=dados['ide'].get('c_uf') or '35',
            aamm='2505',
            cnpj_emitente=emit_cnpj,
            modelo='55',
            serie=numeracao.serie,
            nnf=numeracao.nnf,
            tp_emis='1',
            codigo_numerico=numeracao.codigo_numerico,
        )
        tnfe = montar_tnfe_preliminar(dados, nfe_saida=nf, chave=chave, numeracao=numeracao)
        self.assertIsNotNone(tnfe.infNFe.pag)

    def test_xml_modelo_55_emit_dest_item_impostos(self):
        nf = _nf_pronta()
        xml = gerar_resultado_xml_preliminar(nf)['xml']
        self.assertRegex(xml, r'<[\w:]*mod>55</[\w:]*mod>')
        self.assertRegex(xml, r'<[\w:]*emit>')
        self.assertRegex(xml, r'<[\w:]*dest>')
        self.assertRegex(xml, r'<[\w:]*det[\s>]')
        self.assertRegex(xml, r'<[\w:]*NCM>84818200</[\w:]*NCM>')
        self.assertRegex(xml, r'<[\w:]*CFOP>5102</[\w:]*CFOP>')
        self.assertRegex(xml, r'<[\w:]*ICMS')
        self.assertRegex(xml, r'<[\w:]*ICMSTot>')

    def test_nnf_nao_usa_rascunho_fat(self):
        nf = _nf_pronta()
        self.assertIn('RASCUNHO', (nf.numero or '').upper())
        xml = gerar_resultado_xml_preliminar(nf)['xml']
        self.assertNotIn(f'<nNF>{nf.numero}</nNF>', xml)
        m = re.search(r'<[\w:]*nNF>([0-9]+)</[\w:]*nNF>', xml)
        self.assertIsNotNone(m)
        self.assertTrue(m.group(1).isdigit())
        self.assertEqual(m.group(1), str(nf.pk).zfill(len(m.group(1))))

    def test_chave_44_no_id_inf_nfe(self):
        nf = _nf_pronta()
        xml = gerar_xml_nfe_preliminar(nf).decode('utf-8')
        m = re.search(r'Id="NFe([0-9]{44})"', xml)
        self.assertIsNotNone(m)
        self.assertNotIn('NFePREVIEW', xml)
        self.assertIsNone(re.search(r'<[\w:]*protNFe\b', xml, flags=re.IGNORECASE))

    @override_settings(DANFE_BLOCK_EMISSION_IF_BFR_FAILS=True)
    def test_danfe_bfr_pdf(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        nf = _nf_pronta()
        pdf, meta = gerar_danfe_bfr_nfe_preliminar(nf)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(meta.get('render_engine'), 'brazil_fiscal_report')
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('DANFE', texto)

    def test_pdf_sem_protocolo_fake(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        nf = _nf_pronta()
        pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertNotIn('99999999999999', texto[:500])

    def test_pdf_marca_conferencia_ou_homologacao(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        nf = _nf_pronta()
        pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertTrue(
            'SEMVALORFISCAL' in texto
            or 'HOMOLOGACAO' in texto
            or 'NFECONFERENCIA' in texto,
        )

    def test_nao_transmite_nao_altera_status(self):
        nf = _nf_pronta()
        st = nf.status
        sc = nf.status_conferencia
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        est = AtendimentoEstoque.objects.count()
        gerar_resultado_xml_preliminar(nf)
        if brazil_fiscal_report_disponivel():
            gerar_danfe_bfr_nfe_preliminar(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(nf.status_conferencia, sc)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)
        self.assertEqual(AtendimentoEstoque.objects.count(), est)

    def test_endpoint_preview_xml_preliminar(self):
        nf = _nf_pronta()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-xml-preliminar/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data.get('xml_format'), 'nfelib_4.00_preliminar')
        self.assertEqual(len(res.data.get('chave_acesso_preliminar', '')), 44)

    def test_endpoint_danfe_header_origem(self):
        nf = _nf_pronta()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
        if not brazil_fiscal_report_disponivel():
            self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            return
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.content.startswith(b'%PDF'))
        self.assertEqual(res.get('X-Danfe-Renderer-Oficial'), 'BFR')
        origem = res.get('X-Danfe-Origem', '')
        self.assertIn('xml_preliminar', origem)
