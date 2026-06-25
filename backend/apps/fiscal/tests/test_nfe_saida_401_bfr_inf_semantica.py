"""NF-e 4.0.1 — semântica infCpl / infAdProd para DANFE BFR."""

from __future__ import annotations

import re

from django.test import TestCase, override_settings

from apps.cadastros.models import Cliente
from apps.fiscal.models import ItemNFeSaida
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    brazil_fiscal_report_disponivel,
    gerar_danfe_bfr_nfe_preliminar,
)
from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
    montar_inf_ad_prod_item,
    montar_inf_cpl_nfe,
    montar_inf_cpl_para_danfe,
)
from apps.fiscal.nfe_integracao.nfe_xml_preliminar import gerar_xml_nfe_preliminar
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_401_bfr_preliminar import _nf_pronta, _regra
from apps.regras_fiscais.models import RegraFiscalSaida

TEXTO_REGRA_EXEMPLO = (
    'NAO ACEITAREMOS DEVOLUCAO APOS 7 DIAS DA ENTREGA. A DEVOLUCAO SO PODERA OCORRER '
    'MEDIANTE COMUNICACAO PREVIA E AUTORIZACAO DO DEPARTAMENTO COMERCIAL.'
)
TEXTO_CLIENTE_EXEMPLO = (
    'Endereço de entrega Rua Miguel Langone 341 - Horário de entrega da 7:00 as 15:00 horas'
)
TEXTO_MANUAL_EXEMPLO = 'Instrução manual da conferência para a DANFE'


def _inf_cpl_xml(nf) -> str:
    xml = gerar_xml_nfe_preliminar(nf).decode('utf-8')
    m = re.search(r'<[\w:]*infCpl>([^<]*)</[\w:]*infCpl>', xml, flags=re.IGNORECASE)
    return m.group(1) if m else ''


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DanfeBfrInfSemanticaTests(TestCase):
    def setUp(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        _regra()

    def _regra_5102(self) -> RegraFiscalSaida:
        regra = RegraFiscalSaida.objects.filter(cfop_venda='5102').first()
        self.assertIsNotNone(regra)
        return regra

    def test_inf_cpl_quatro_origens_ordem_e_maiusculas(self):
        regra = self._regra_5102()
        regra.informacoes_complementares = TEXTO_REGRA_EXEMPLO
        regra.save(update_fields=['informacoes_complementares'])
        nf = _nf_pronta()
        cliente = nf.cliente
        cliente.informacoes_complementares_nfe = TEXTO_CLIENTE_EXEMPLO
        cliente.save(update_fields=['informacoes_complementares_nfe'])
        nf.informacoes_adicionais = TEXTO_MANUAL_EXEMPLO
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['informacoes_adicionais', 'pedido_cliente_numero'])

        inf_cpl_danfe = montar_inf_cpl_para_danfe(nf)
        linhas = [ln for ln in inf_cpl_danfe.split('\n') if ln.strip()]
        self.assertGreaterEqual(len(linhas), 4)
        self.assertIn('COMUNICACAO PREVIA', linhas[0])
        self.assertIn('MIGUEL LANGONE', linhas[1])
        self.assertIn('INSTRU', linhas[2])
        self.assertEqual(linhas[3], 'PEDIDO DE COMPRA: 5050')
        self.assertEqual(inf_cpl_danfe, inf_cpl_danfe.upper())

        inf_cpl_xml, _ = montar_inf_cpl_nfe(nf)
        self.assertNotIn('\n', inf_cpl_xml)
        self.assertIn('PEDIDO DE COMPRA: 5050', inf_cpl_xml)

    def test_inf_cpl_contem_informacoes_complementares_regra(self):
        regra = self._regra_5102()
        regra.informacoes_complementares = TEXTO_REGRA_EXEMPLO
        regra.save(update_fields=['informacoes_complementares'])
        inf_cpl, _ = montar_inf_cpl_nfe(_nf_pronta())
        self.assertIn('COMUNICACAO PREVIA', inf_cpl)

    def test_inf_cpl_contem_informacao_cliente(self):
        nf = _nf_pronta()
        nf.cliente.informacoes_complementares_nfe = TEXTO_CLIENTE_EXEMPLO
        nf.cliente.save(update_fields=['informacoes_complementares_nfe'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertIn('MIGUEL LANGONE', inf_cpl)

    def test_inf_cpl_xml_sem_quebra_linha(self):
        regra = self._regra_5102()
        regra.informacoes_complementares = TEXTO_REGRA_EXEMPLO
        regra.save(update_fields=['informacoes_complementares'])
        nf = _nf_pronta()
        nf.informacoes_adicionais = TEXTO_MANUAL_EXEMPLO
        nf.pedido_cliente_numero = '42287'
        nf.save(update_fields=['informacoes_adicionais', 'pedido_cliente_numero'])

        inf_cpl_xml = _inf_cpl_xml(nf)
        self.assertNotIn('\n', inf_cpl_xml)
        self.assertIn('PEDIDO DE COMPRA: 42287', inf_cpl_xml)
        self.assertIn('COMUNICACAO PREVIA', inf_cpl_xml)

    def test_inf_cpl_contem_manual_nf(self):
        nf = _nf_pronta()
        nf.informacoes_adicionais = TEXTO_MANUAL_EXEMPLO
        nf.save(update_fields=['informacoes_adicionais'])
        inf_cpl = _inf_cpl_xml(nf)
        self.assertIn('INSTRU', inf_cpl.upper())

    def test_inf_cpl_contem_pedido_cliente_linha_separada(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['pedido_cliente_numero'])
        inf_cpl_xml, _ = montar_inf_cpl_nfe(nf)
        inf_cpl_danfe = montar_inf_cpl_para_danfe(nf)
        self.assertIn('PEDIDO DE COMPRA: 5050', inf_cpl_xml)
        self.assertNotIn('\n', inf_cpl_xml)
        self.assertIn('\n', inf_cpl_danfe)

    def test_inf_cpl_nao_contem_cst_csosn(self):
        regra = self._regra_5102()
        regra.cst_icms = '00'
        regra.save(update_fields=['cst_icms'])
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['pedido_cliente_numero'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        up = inf_cpl.upper()
        self.assertNotIn('CST/CSOSN', up)
        self.assertNotIn('CST ICMS', up)
        self.assertNotIn('CSOSN', up)

    def test_inf_cpl_sem_texto_status_danfe(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['pedido_cliente_numero'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        low = inf_cpl.lower()
        self.assertNotIn('nf-e de conferência', low)
        self.assertNotIn('sem valor fiscal', low)
        self.assertNotIn('sem protocolo de autorização', low)

    def test_inf_cpl_nao_usa_observacoes_regra_nem_observacoes_nfe(self):
        regra = self._regra_5102()
        regra.informacoes_complementares = ''
        regra.observacoes = 'Observação da regra — não deve sair.'
        regra.save(update_fields=['informacoes_complementares', 'observacoes'])
        nf = _nf_pronta()
        nf.observacoes_nfe = 'Obs NF — não deve sair.'
        nf.save(update_fields=['observacoes_nfe'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertNotIn('Observação da regra', inf_cpl)
        self.assertNotIn('Obs NF', inf_cpl)

    def test_inf_cpl_cliente_vazio_nao_aparece(self):
        nf = _nf_pronta()
        Cliente.objects.filter(pk=nf.cliente_id).update(informacoes_complementares_nfe='')
        nf.refresh_from_db()
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertNotIn('MIGUEL LANGONE', inf_cpl)

    def test_inf_cpl_pedido_cabecalho_sem_item(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['pedido_cliente_numero'])
        inf_cpl = _inf_cpl_xml(nf)
        self.assertIn('PEDIDO DE COMPRA: 5050', inf_cpl)
        xml = gerar_xml_nfe_preliminar(nf).decode('utf-8')
        self.assertRegex(xml, r'<[\w:]*xPed>5050</[\w:]*xPed>')

    def test_inf_ad_prod_sem_pedido_cabecalho(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['pedido_cliente_numero'])
        item = nf.itens.first()
        texto = montar_inf_ad_prod_item(nf, {'item_id': item.pk}, item)
        self.assertEqual(texto, '')

    def test_inf_ad_prod_com_pedido_item(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = ''
        nf.save(update_fields=['pedido_cliente_numero'])
        item = nf.itens.first()
        item.pedido_cliente_numero = '5050'
        item.pedido_cliente_item = '3'
        item.observacao_item = 'Lote conferência A1'
        item.save(update_fields=['pedido_cliente_numero', 'pedido_cliente_item', 'observacao_item'])
        texto = montar_inf_ad_prod_item(nf, {'item_id': item.pk}, item)
        self.assertIn('Pedido de compra: 5050', texto)
        self.assertIn('Item: 3', texto)

    def test_campo_manual_aparece_na_conferencia(self):
        nf = _nf_pronta()
        nf.informacoes_adicionais = TEXTO_MANUAL_EXEMPLO
        nf.save(update_fields=['informacoes_adicionais'])
        conf = montar_conferencia_nfe_saida(nf)
        self.assertIn(TEXTO_MANUAL_EXEMPLO, conf['observacoes']['informacoes_adicionais'])

    def test_inf_cpl_deduplica_textos_iguais(self):
        regra = self._regra_5102()
        texto = 'MESMA OBSERVACAO FISCAL UNICA.'
        regra.informacoes_complementares = texto
        regra.save(update_fields=['informacoes_complementares'])
        nf = _nf_pronta()
        nf.informacoes_adicionais = texto
        nf.save(update_fields=['informacoes_adicionais'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertEqual(inf_cpl.count('MESMA OBSERVACAO FISCAL UNICA'), 1)

    def test_observacoes_internas_nao_aparecem(self):
        nf = _nf_pronta()
        nf.observacoes_internas = 'SEGREDO ERP INTERNO'
        nf.save(update_fields=['observacoes_internas'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertNotIn('SEGREDO', inf_cpl)

    def test_danfe_continua_gerando(self):
        nf = _nf_pronta()
        pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_pdf_manual_nf_no_infcpl(self):
        nf = _nf_pronta()
        nf.informacoes_adicionais = 'ENDERECO ENTREGA DOC A'
        nf.save(update_fields=['informacoes_adicionais'])
        pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('ENDERECOENTREGADOCA', texto.replace(' ', ''))
