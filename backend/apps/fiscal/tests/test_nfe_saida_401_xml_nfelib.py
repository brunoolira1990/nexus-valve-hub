"""NF-e Saída 4.0.1 — XML oficial NF-e 4.00 via nfelib (sem SEFAZ)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.models import AtendimentoEstoque, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_xml_nfelib import gerar_xml_oficial_nfe_saida
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item


def _nf_rascunho() -> NFeSaida:
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
    nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
    nf.informacoes_adicionais = 'Info compl XML oficial'
    nf.informacoes_fisco = 'Texto fisco XML'
    nf.observacoes_internas = 'NAO DEVE SAIR NO XML'
    nf.save(update_fields=['informacoes_adicionais', 'informacoes_fisco', 'observacoes_internas'])
    return nf


class NFeSaida401XmlNfelibTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe401', 'nfe401@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_nfelib_instalado(self):
        self.assertTrue(nfelib_disponivel())

    def test_xml_oficial_estrutura(self):
        nf = _nf_rascunho()
        data = gerar_xml_oficial_nfe_saida(nf)
        self.assertFalse(data.get('bloqueado'))
        self.assertEqual(data.get('xml_format'), 'nfelib_4.00')
        xml = data['xml']
        self.assertIn('<?xml', xml)
        self.assertIn('portalfiscal.inf.br/nfe', xml)
        self.assertIn('infNFe', xml)
        self.assertIn('versao="4.00"', xml)
        self.assertIn('NFePREVIEW', xml)
        self.assertIn('tpAmb', xml)
        self.assertRegex(xml.replace(' ', ''), r'tpAmb>2<')
        self.assertNotIn('protNFe', xml)
        self.assertNotIn('NAO DEVE SAIR', xml)
        self.assertIn('Info compl XML oficial', xml)
        self.assertIn('84818200', xml)

    def test_id_preview_nao_e_chave_44(self):
        nf = _nf_rascunho()
        xml = gerar_xml_oficial_nfe_saida(nf)['xml']
        import re

        m = re.search(r'Id="(NFe[^"]+)"', xml)
        self.assertIsNotNone(m)
        chave_body = m.group(1)[3:] if m else ''
        self.assertNotEqual(len(chave_body), 44)

    def test_nao_altera_status_eventos_estoque(self):
        nf = _nf_rascunho()
        st = nf.status
        sc = nf.status_conferencia
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        est = AtendimentoEstoque.objects.count()
        gerar_xml_oficial_nfe_saida(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(nf.status_conferencia, sc)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)
        self.assertEqual(AtendimentoEstoque.objects.count(), est)

    def test_endpoint_preview_xml_oficial(self):
        nf = _nf_rascunho()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-xml-oficial/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data.get('xml_format'), 'nfelib_4.00')
        self.assertIn('NFePREVIEW', res.data.get('xml', ''))

    def test_preview_xml_simplificado_inalterado(self):
        nf = _nf_rascunho()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-xml/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn('xml_format', res.data)
        self.assertIn('XML DE PRÉVIA', res.data.get('xml', ''))
