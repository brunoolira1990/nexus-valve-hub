"""NF-e 4.0.1 — acabamento DANFE BrazilFiscalReport (marca d'água, infCpl, logo)."""

from __future__ import annotations

import re
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.fiscal.models import AtendimentoEstoque, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    brazil_fiscal_report_disponivel,
    gerar_danfe_bfr_nfe_preliminar,
)
from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
    montar_inf_ad_prod_item,
    montar_inf_cpl_nfe,
)
from apps.fiscal.nfe_integracao.danfe_marca_dagua import resolver_marca_dagua_danfe
from apps.fiscal.nfe_integracao.nfe_xml_preliminar import gerar_xml_nfe_preliminar
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_401_bfr_preliminar import _nf_pronta, _regra
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _pdf_texto(nf: NFeSaida) -> str:
    pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
    return compact_pdf_text(pdf_text(pdf))


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DanfeBfrAcabamentoTests(TestCase):
    def setUp(self):
        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')

    def test_resolver_marca_dagua_conferencia(self):
        nf = _nf_pronta()
        marca = resolver_marca_dagua_danfe(nf, '2', tem_protocolo=False)
        self.assertIn('CONFERÊNCIA', marca or '')
        self.assertIn('SEM VALOR FISCAL', marca or '')
        self.assertNotIn('CANCELADA', (marca or '').split('\n')[0])

    def test_resolver_marca_dagua_cancelada_homolog(self):
        nf = _nf_pronta()
        nf.status = 'CANCELADA_INTERNA'
        marca = resolver_marca_dagua_danfe(nf, '2', tem_protocolo=False)
        self.assertIn('CANCELADA', marca or '')

    def test_inf_cpl_enxuto_sem_xml_preliminar(self):
        nf = _nf_pronta()
        regra = RegraFiscalSaida.objects.filter(cfop_venda='5102').first()
        regra.informacoes_complementares = 'Texto fiscal permitido na DANFE.'
        regra.save(update_fields=['informacoes_complementares'])
        nf.observacoes_internas = 'SEGREDO INTERNO ERP'
        nf.informacoes_adicionais = 'Instrução manual conferência DANFE.'
        nf.pedido_cliente_numero = '5050'
        nf.save(
            update_fields=[
                'informacoes_adicionais',
                'observacoes_internas',
                'pedido_cliente_numero',
            ],
        )
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertNotIn('NF-e DE CONFERÊNCIA', inf_cpl)
        self.assertNotIn('SEM VALOR FISCAL', inf_cpl.upper())
        self.assertNotIn('SEM PROTOCOLO', inf_cpl.upper())
        self.assertNotIn('CST/CSOSN', inf_cpl.upper())
        self.assertIn('PEDIDO DO CLIENTE: 5050', inf_cpl)
        self.assertIn('TEXTO FISCAL PERMITIDO', inf_cpl)
        self.assertIn('INSTRUÇÃO MANUAL'.replace('Ç', 'C'), inf_cpl.replace('Ç', 'C'))
        self.assertLess(len(inf_cpl), 420)
        self.assertNotIn('XML preliminar', inf_cpl)
        self.assertNotIn('não transmitir', inf_cpl.lower())
        self.assertNotIn('SEGREDO', inf_cpl)
        self.assertNotIn('Condição de pagamento', inf_cpl)
        self.assertNotIn('Prazo de pagamento', inf_cpl)

    def test_inf_cpl_sem_condicao_e_prazo_pagamento(self):
        nf = _nf_pronta()
        nf.condicao_pagamento_texto = '30/60/90 dias'
        nf.dias_parcelas = [30, 60, 90]
        nf.save(update_fields=['condicao_pagamento_texto', 'dias_parcelas'])
        inf_cpl, _ = montar_inf_cpl_nfe(nf)
        self.assertNotIn('Condição de pagamento', inf_cpl)
        self.assertNotIn('Prazo de pagamento', inf_cpl)
        self.assertNotIn('30/60', inf_cpl)

    def test_xml_inf_ad_prod_separado_de_infcpl(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = ''
        nf.save(update_fields=['pedido_cliente_numero'])
        item = nf.itens.first()
        item.observacao_item = 'Observacao especifica do item'
        item.pedido_cliente_numero = '5050'
        item.pedido_cliente_item = '2'
        item.save(update_fields=['observacao_item', 'pedido_cliente_numero', 'pedido_cliente_item'])
        xml = gerar_xml_nfe_preliminar(nf).decode('utf-8')
        self.assertRegex(xml, r'<[\w:]*infAdProd>[^<]*Observacao especifica[^<]*</[\w:]*infAdProd>')
        self.assertRegex(xml, r'<[\w:]*xPed>5050</[\w:]*xPed>')
        m_cpl = re.search(r'<[\w:]*infCpl>([^<]*)</[\w:]*infCpl>', xml, flags=re.IGNORECASE)
        if m_cpl:
            inf_cpl = m_cpl.group(1)
            self.assertNotIn('Observacao especifica', inf_cpl)
            self.assertNotIn('Condição de pagamento', inf_cpl)
            self.assertNotIn('Pedido do cliente', inf_cpl)

    def test_inf_ad_prod_nao_contem_pagamento(self):
        nf = _nf_pronta()
        nf.condicao_pagamento_texto = 'A vista'
        item = nf.itens.first()
        texto = montar_inf_ad_prod_item(nf, {'item_id': item.pk}, item)
        self.assertNotIn('pagamento', texto.lower())
        self.assertNotIn('Condição', texto)

    def test_xml_preliminar_inf_cpl_sem_tecnico(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.observacoes_internas = 'NAO DEVE SAIR'
        nf.save(update_fields=['pedido_cliente_numero', 'observacoes_internas'])
        xml = gerar_xml_nfe_preliminar(nf).decode('utf-8')
        self.assertIn('PEDIDO DO CLIENTE: 5050', xml)
        m = re.search(r'<[\w:]*infCpl>([^<]*)</[\w:]*infCpl>', xml, flags=re.IGNORECASE)
        self.assertIsNotNone(m)
        inf_cpl = m.group(1)
        self.assertNotIn('não transmitir', inf_cpl.lower())
        self.assertNotIn('NAO DEVE SAIR', inf_cpl)
        self.assertNotIn('RASCUNHO-FAT', inf_cpl)

    def test_pdf_nao_contem_cancelada_em_conferencia(self):
        nf = _nf_pronta()
        texto = _pdf_texto(nf)
        self.assertNotIn('CANCELADA', texto)
        self.assertIn('SEMVALORFISCAL', texto)
        self.assertTrue(
            'NFECONFERENCIA' in texto or 'CONFERENCIA' in texto or 'HOMOLOGACAO' in texto,
        )

    def test_pdf_sem_continuacao_inf_cpl_na_area_produtos(self):
        nf = _nf_pronta()
        regra = RegraFiscalSaida.objects.filter(cfop_venda='5102').first()
        regra.informacoes_complementares = 'Texto fiscal curto permitido.'
        regra.save(update_fields=['informacoes_complementares'])
        texto = _pdf_texto(nf)
        norm = texto.replace('Ç', 'C').replace('Ã', 'A').replace('Õ', 'O')
        self.assertNotIn('CONTINUACAO', norm)
        self.assertNotIn('CONTINUACAODASINFORMACOES', norm)

    def test_pdf_contem_pedido_cliente_cabecalho(self):
        nf = _nf_pronta()
        nf.pedido_cliente_numero = '5050'
        nf.save(update_fields=['pedido_cliente_numero'])
        texto = _pdf_texto(nf)
        self.assertIn('5050', texto)
        self.assertNotIn('CONDICAODEPAGAMENTO', texto)

    def test_pdf_nao_contem_observacoes_internas(self):
        nf = _nf_pronta()
        nf.observacoes_internas = 'OBSERVACAO INTERNA SECRETA'
        nf.save(update_fields=['observacoes_internas'])
        texto = _pdf_texto(nf)
        self.assertNotIn('OBSERVACAOINTERNASECRETA', texto)

    def test_pdf_sem_protocolo_fake(self):
        nf = _nf_pronta()
        texto = _pdf_texto(nf)
        self.assertNotIn('99999999999999', texto[:800])

    @mock.patch('apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report.get_emitente_logo_nfe_saida')
    def test_logo_quando_disponivel(self, mock_logo):
        import tempfile

        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            path = tmp.name
        try:
            Image.new('RGB', (80, 40), color=(30, 60, 120)).save(path)
            mock_logo.return_value = path
            nf = _nf_pronta()
            pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
            self.assertTrue(pdf.startswith(b'%PDF'))
            mock_logo.assert_called()
        finally:
            import os

            if os.path.isfile(path):
                os.unlink(path)

    def test_sem_logo_gera_normalmente(self):
        nf = _nf_pronta()
        pdf, _ = gerar_danfe_bfr_nfe_preliminar(nf)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_geracao_nao_altera_status_estoque_eventos(self):
        nf = _nf_pronta()
        st = nf.status
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        est = AtendimentoEstoque.objects.count()
        gerar_danfe_bfr_nfe_preliminar(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)
        self.assertEqual(AtendimentoEstoque.objects.count(), est)

    def test_marca_dagua_cancelada_para_bfr(self):
        nf = _nf_pronta()
        nf.status = 'CANCELADA_INTERNA'
        marca = resolver_marca_dagua_danfe(nf, '2', tem_protocolo=False)
        self.assertIn('CANCELADA', marca or '')


class DanfeMarcaDaguaUnitTests(TestCase):
    def test_autorizada_producao_sem_marca(self):
        nf = NFeSaida(status='AUTORIZADA_INTERNA')
        self.assertIsNone(resolver_marca_dagua_danfe(nf, '1', tem_protocolo=True))

    def test_autorizada_homolog_sem_valor(self):
        nf = NFeSaida(status='AUTORIZADA_INTERNA')
        marca = resolver_marca_dagua_danfe(nf, '2', tem_protocolo=True)
        self.assertEqual(marca, 'SEM VALOR FISCAL')
