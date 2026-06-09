"""Parser retorno SEFAZ — cStat 104 lote vs infProt NF-e."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.resposta import montar_resposta_emissao_homologacao
from apps.fiscal.nfe_emissao.retorno_sefaz import (
    processar_retorno_autorizacao_nfe,
    resultado_autorizacao_mock,
)
from apps.fiscal.nfe_emissao.servico import reprocessar_retorno_nfe_homologacao
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf, _preparar_pronta

XML_LOTE_104_REJEICAO_225 = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4"><retEnviNFe versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe"><tpAmb>2</tpAmb><cStat>104</cStat><xMotivo>Lote processado</xMotivo><dhRecbto>2026-05-23T15:05:57-03:00</dhRecbto><protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><cStat>225</cStat><xMotivo>Rejeição: Falha no Schema XML do lote de NFe</xMotivo><dhRecbto>2026-05-23T15:05:57-03:00</dhRecbto></infProt></protNFe></retEnviNFe></nfeResultMsg></soap:Body></soap:Envelope>"""

XML_LOTE_104_AUTORIZADO_100 = """<?xml version="1.0" encoding="utf-8"?><retEnviNFe versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe"><cStat>104</cStat><xMotivo>Lote processado</xMotivo><protNFe versao="4.00"><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo><nProt>135260000000099</nProt><chNFe>35260512345678000199550090000000021000000021</chNFe></infProt></protNFe></retEnviNFe>"""

XML_LOTE_104_SEM_PROT = """<?xml version="1.0" encoding="utf-8"?><retEnviNFe versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe"><cStat>104</cStat><xMotivo>Lote processado</xMotivo></retEnviNFe>"""

XML_LOTE_103 = """<?xml version="1.0" encoding="utf-8"?><retEnviNFe versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe"><cStat>103</cStat><xMotivo>Lote recebido com sucesso</xMotivo><infRec><nRec>135260000000888</nRec></infRec></retEnviNFe>"""

XML_LOTE_105 = """<?xml version="1.0" encoding="utf-8"?><retEnviNFe versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe"><cStat>105</cStat><xMotivo>Lote em processamento</xMotivo></retEnviNFe>"""


class NFe402RetornoCstat104Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe104', 'nfe104@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _preparar_pronta(self.nf, self.user)

    def test_lote_104_infprot_100_autorizado(self):
        r = processar_retorno_autorizacao_nfe(XML_LOTE_104_AUTORIZADO_100)
        self.assertEqual(r.lote.c_stat, '104')
        self.assertEqual(r.nfe.c_stat, '100')
        self.assertTrue(r.autorizado)
        self.assertEqual(r.status_final, NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO)
        self.assertEqual(r.protocolo, '135260000000099')

    def test_lote_104_infprot_225_rejeitada(self):
        r = processar_retorno_autorizacao_nfe(XML_LOTE_104_REJEICAO_225)
        self.assertEqual(r.lote.c_stat, '104')
        self.assertEqual(r.lote.x_motivo, 'Lote processado')
        self.assertEqual(r.nfe.c_stat, '225')
        self.assertFalse(r.autorizado)
        self.assertTrue(r.rejeitado)
        self.assertEqual(r.status_final, NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO)
        self.assertNotEqual(r.c_stat, '104')

    def test_lote_104_sem_prot_nao_autoriza_nem_rejeita_final(self):
        r = processar_retorno_autorizacao_nfe(XML_LOTE_104_SEM_PROT)
        self.assertEqual(r.status_final, 'LOTE_PROCESSADO_SEM_PROTOCOLO')
        self.assertFalse(r.autorizado)
        self.assertFalse(r.rejeitado)

    def test_lote_103_aguardando(self):
        r = processar_retorno_autorizacao_nfe(XML_LOTE_103)
        self.assertEqual(r.status_final, 'AGUARDANDO_PROCESSAMENTO')
        self.assertEqual(r.lote.recibo, '135260000000888')

    def test_lote_105_aguardando(self):
        r = processar_retorno_autorizacao_nfe(XML_LOTE_105)
        self.assertEqual(r.status_final, 'AGUARDANDO_PROCESSAMENTO')

    def test_json_separa_lote_e_nfe(self):
        r = processar_retorno_autorizacao_nfe(XML_LOTE_104_REJEICAO_225)
        payload = montar_resposta_emissao_homologacao(self.nf, ok=False, resultado=r, mensagem='x')
        self.assertEqual(payload['lote']['cstat'], '104')
        self.assertEqual(payload['nfe']['cstat'], '225')

    def test_reprocessar_retorno_salvo_nf2(self):
        self.nf.xml_retorno = XML_LOTE_104_REJEICAO_225
        self.nf.xml_assinado = '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1" versao="4.00"/></NFe>'
        self.nf.cstat_autorizacao = '104'
        self.nf.motivo_autorizacao = 'Lote processado'
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO
        self.nf.serie_nfe = '900'
        self.nf.numero_nfe = '000000002'
        self.nf.save()

        res = reprocessar_retorno_nfe_homologacao(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.cstat_lote, '104')
        self.assertEqual(self.nf.cstat_autorizacao, '225')
        self.assertEqual(self.nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO)
        self.assertEqual(res['lote']['cstat'], '104')
        self.assertEqual(res['nfe']['cstat'], '225')
        self.assertIn('225', res['mensagem'])

    def test_api_reprocessar_retorno(self):
        self.nf.xml_retorno = XML_LOTE_104_REJEICAO_225
        self.nf.cstat_autorizacao = '104'
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO
        self.nf.save()
        res = self.client.post(f'/api/nf-saidas/{self.nf.pk}/reprocessar-retorno-sefaz/', {}, format='json')
        self.assertIn(res.status_code, (200, 422))
        body = res.json()
        self.assertEqual(body['lote']['cstat'], '104')
        self.assertEqual(body['nfe']['cstat'], '225')

    def test_resultado_mock_compat(self):
        m = resultado_autorizacao_mock(autorizado=True, c_stat='100', protocolo='123')
        self.assertTrue(m.autorizado)
        self.assertEqual(m.c_stat, '100')
