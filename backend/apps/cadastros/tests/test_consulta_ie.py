"""Testes da consulta de IE via SEFAZ NFeConsultaCadastro."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cadastros.consulta_ie import ConsultaIeError, consultar_inscricao_estadual
from apps.cadastros.views import consulta_ie
from apps.fiscal.nfe_integracao.adapters.consulta_cadastro_parser import parse_consulta_cadastro_response
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import consulta_cadastro_contribuinte

XML_IE_ATIVA = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <retConsCad xmlns="http://www.portalfiscal.inf.br/nfe" versao="2.00">
      <infCons>
        <cStat>111</cStat>
        <xMotivo>Consulta cadastro com uma ocorrencia</xMotivo>
        <UF>SP</UF>
        <CNPJ>00000000000191</CNPJ>
      </infCons>
      <infCad>
        <IE>123456789012</IE>
        <CNPJ>00000000000191</CNPJ>
        <UF>SP</UF>
        <cSit>1</cSit>
        <xNome>EMPRESA TESTE LTDA</xNome>
        <xMun>SAO PAULO</xMun>
        <CNAE>2511000</CNAE>
      </infCad>
    </retConsCad>
  </soap:Body>
</soap:Envelope>"""

XML_MULTIPLAS_IE = """<?xml version="1.0" encoding="utf-8"?>
<retConsCad xmlns="http://www.portalfiscal.inf.br/nfe" versao="2.00">
  <infCons>
    <cStat>112</cStat>
    <xMotivo>Consulta cadastro com mais de uma ocorrencia</xMotivo>
    <UF>SP</UF>
    <CNPJ>00000000000191</CNPJ>
  </infCons>
  <infCad>
    <IE>111111111111</IE>
    <UF>SP</UF>
    <cSit>0</cSit>
    <xNome>EMPRESA TESTE LTDA</xNome>
  </infCad>
  <infCad>
    <IE>222222222222</IE>
    <UF>SP</UF>
    <cSit>1</cSit>
    <xNome>EMPRESA TESTE LTDA</xNome>
  </infCad>
</retConsCad>"""

XML_IE_NAO_ENCONTRADA = """<?xml version="1.0" encoding="utf-8"?>
<retConsCad xmlns="http://www.portalfiscal.inf.br/nfe" versao="2.00">
  <infCons>
    <cStat>257</cStat>
    <xMotivo>CNPJ nao cadastrado na UF</xMotivo>
    <UF>SP</UF>
    <CNPJ>00000000000191</CNPJ>
  </infCons>
</retConsCad>"""

XML_IE_ANINHADA_INFCONS = """<?xml version="1.0" encoding="utf-8"?>
<retConsCad xmlns="http://www.portalfiscal.inf.br/nfe" versao="2.00">
  <infCons>
    <cStat>111</cStat>
    <xMotivo>Consulta cadastro com uma ocorrencia</xMotivo>
    <UF>SP</UF>
    <CNPJ>00000000000191</CNPJ>
    <infCad>
      <IE>987654321098</IE>
      <CNPJ>00000000000191</CNPJ>
      <UF>SP</UF>
      <cSit>1</cSit>
      <xNome>EMPRESA TESTE LTDA</xNome>
    </infCad>
  </infCons>
</retConsCad>"""

XML_IE_MG_WSDL = """<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://www.w3.org/2003/05/soap-envelope">
  <S:Body>
    <consultaCadastro4Result xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/CadConsultaCadastro4">
      <retConsCad versao="2.00">
        <infCons xmlns="http://www.portalfiscal.inf.br/nfe">
          <cStat>111</cStat>
          <xMotivo>Consulta cadastro com uma ocorrencia</xMotivo>
          <UF>MG</UF>
          <CNPJ>01838723043012</CNPJ>
          <infCad>
            <IE>0010870822926</IE>
            <CNPJ>01838723043012</CNPJ>
            <UF>MG</UF>
            <cSit>1</cSit>
            <xNome>BRF - BRASIL FOODS S.A</xNome>
            <ender><xMun>UBERLANDIA</xMun></ender>
          </infCad>
        </infCons>
      </retConsCad>
    </consultaCadastro4Result>
  </S:Body>
</S:Envelope>"""


class ConsultaCadastroParserTests(SimpleTestCase):
    def test_normaliza_ie_ativa(self):
        parsed = parse_consulta_cadastro_response(XML_IE_ATIVA, cnpj='00000000000191', uf='SP')
        self.assertTrue(parsed.sucesso)
        self.assertEqual(parsed.inscricao_estadual, '123456789012')
        self.assertEqual(parsed.situacao_ie, 'Habilitado')

    def test_multiplas_ies_prioriza_habilitada(self):
        parsed = parse_consulta_cadastro_response(XML_MULTIPLAS_IE, cnpj='00000000000191', uf='SP')
        self.assertTrue(parsed.sucesso)
        self.assertEqual(len(parsed.inscricoes_estaduais), 2)
        self.assertEqual(parsed.inscricao_estadual, '222222222222')

    def test_ie_nao_encontrada(self):
        parsed = parse_consulta_cadastro_response(XML_IE_NAO_ENCONTRADA, cnpj='00000000000191', uf='SP')
        self.assertFalse(parsed.sucesso)
        self.assertEqual(parsed.erro_codigo, 'IE_NAO_LOCALIZADA')

    def test_ie_aninhada_em_infcons(self):
        parsed = parse_consulta_cadastro_response(XML_IE_ANINHADA_INFCONS, cnpj='00000000000191', uf='SP')
        self.assertTrue(parsed.sucesso)
        self.assertEqual(parsed.inscricao_estadual, '987654321098')

    def test_ie_mg_envelope_wsdl(self):
        parsed = parse_consulta_cadastro_response(XML_IE_MG_WSDL, cnpj='01838723043012', uf='MG')
        self.assertTrue(parsed.sucesso)
        self.assertEqual(parsed.inscricao_estadual, '0010870822926')
        self.assertEqual(parsed.municipio, 'UBERLANDIA')


class ConsultaCadastroAdapterTests(SimpleTestCase):
    def test_preserva_cnpj_alfanumerico_no_documento_sefaz(self):
        class ComunicacaoFake:
            def __init__(self):
                self.chamada = None

            def consulta_cadastro(self, modelo, documento, *, tipo, uf):
                self.chamada = (modelo, documento, tipo, uf)
                return MagicMock(text=XML_IE_ATIVA)

        comunicacao = ComunicacaoFake()
        consulta_cadastro_contribuinte(
            comunicacao,
            '00.000.000/E08G-12',
            uf='sp',
        )

        self.assertEqual(comunicacao.chamada, ('nfe', '00000000E08G12', 'CNPJ', 'SP'))


class ConsultaIeServicoTests(SimpleTestCase):
    def test_rejeita_cnpj_invalido(self):
        with self.assertRaises(ConsultaIeError) as ctx:
            consultar_inscricao_estadual('11.111.111/1111-11', 'SP')
        self.assertEqual(ctx.exception.codigo, 'CNPJ_INVALIDO')

    def test_uf_obrigatoria(self):
        with self.assertRaises(ConsultaIeError) as ctx:
            consultar_inscricao_estadual('00.000.000/0001-91', '')
        self.assertEqual(ctx.exception.codigo, 'UF_OBRIGATORIA')

    @patch('apps.cadastros.consulta_ie._resolver_empresa')
    def test_certificado_nao_configurado(self, mock_empresa):
        mock_empresa.side_effect = ConsultaIeError(
            'Certificado digital não configurado para consulta SEFAZ.',
            'CERTIFICADO_NAO_CONFIGURADO',
        )
        with self.assertRaises(ConsultaIeError) as ctx:
            consultar_inscricao_estadual('00.000.000/0001-91', 'SP')
        self.assertEqual(ctx.exception.codigo, 'CERTIFICADO_NAO_CONFIGURADO')

    @patch('apps.cadastros.consulta_ie.consulta_cadastro_contribuinte')
    @patch('apps.cadastros.consulta_ie.criar_comunicacao_sefaz')
    @patch('apps.cadastros.consulta_ie.carregar_certificado_empresa')
    @patch('apps.cadastros.consulta_ie.validar_prontidao_consulta_sefaz', return_value=(True, '', ''))
    @patch('apps.cadastros.consulta_ie._resolver_empresa')
    def test_consulta_mockada_com_ie(
        self,
        mock_empresa,
        _mock_prontidao,
        mock_cert,
        _mock_com,
        mock_consulta,
    ):
        empresa = MagicMock()
        empresa.senha_certificado = 'senha'
        empresa.nfe_ambiente = 'homologacao'
        mock_empresa.return_value = empresa
        cert = MagicMock()
        cert.valido = True
        cert.caminho = '/tmp/cert-teste.pfx'
        mock_cert.return_value = cert
        mock_consulta.return_value = MagicMock(text=XML_IE_ATIVA)

        payload = consultar_inscricao_estadual('00.000.000/0001-91', 'SP', empresa_id=1)
        self.assertTrue(payload['sucesso'])
        self.assertEqual(payload['inscricao_estadual'], '123456789012')
        self.assertEqual(payload['fonte'], 'SEFAZ_NFE_CONSULTA_CADASTRO')

    @patch('apps.cadastros.consulta_ie.consulta_cadastro_contribuinte')
    @patch('apps.cadastros.consulta_ie.criar_comunicacao_sefaz')
    @patch('apps.cadastros.consulta_ie.carregar_certificado_empresa')
    @patch('apps.cadastros.consulta_ie.validar_prontidao_consulta_sefaz', return_value=(True, '', ''))
    @patch('apps.cadastros.consulta_ie._resolver_empresa')
    def test_consulta_mockada_com_ie_alfanumerico(
        self,
        mock_empresa,
        _mock_prontidao,
        mock_cert,
        _mock_com,
        mock_consulta,
    ):
        empresa = MagicMock()
        empresa.senha_certificado = 'senha'
        empresa.nfe_ambiente = 'homologacao'
        mock_empresa.return_value = empresa
        cert = MagicMock()
        cert.valido = True
        cert.caminho = '/tmp/cert-teste.pfx'
        mock_cert.return_value = cert
        mock_consulta.return_value = MagicMock(text=XML_IE_ATIVA)

        payload = consultar_inscricao_estadual('00.000.000/E08G-12', 'SP', empresa_id=1)

        self.assertTrue(payload['sucesso'])
        self.assertEqual(payload['inscricao_estadual'], '123456789012')
        self.assertEqual(mock_consulta.call_args.args[1], '00000000E08G12')

    @patch('apps.cadastros.consulta_ie.consulta_cadastro_contribuinte', side_effect=Exception('timeout'))
    @patch('apps.cadastros.consulta_ie.criar_comunicacao_sefaz')
    @patch('apps.cadastros.consulta_ie.carregar_certificado_empresa')
    @patch('apps.cadastros.consulta_ie.validar_prontidao_consulta_sefaz', return_value=(True, '', ''))
    @patch('apps.cadastros.consulta_ie._resolver_empresa')
    def test_falha_sefaz_amigavel(
        self,
        mock_empresa,
        _mock_prontidao,
        mock_cert,
        _mock_com,
        _mock_consulta,
    ):
        from apps.fiscal.nfe_integracao.adapters.exceptions import PyNFeComunicacaoError

        empresa = MagicMock()
        empresa.senha_certificado = 'senha'
        empresa.nfe_ambiente = 'homologacao'
        mock_empresa.return_value = empresa
        cert = MagicMock()
        cert.valido = True
        cert.caminho = '/tmp/cert-teste.pfx'
        mock_cert.return_value = cert

        with patch(
            'apps.cadastros.consulta_ie.consulta_cadastro_contribuinte',
            side_effect=PyNFeComunicacaoError('timeout'),
        ):
            payload = consultar_inscricao_estadual('00.000.000/0001-91', 'SP', empresa_id=1)

        self.assertFalse(payload['sucesso'])
        self.assertIn('indisponível', payload['mensagem_usuario'].lower())


class ConsultaIeEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        user_model = get_user_model()
        self.user = user_model(username='tester')

    def test_endpoint_exige_autenticacao(self):
        request = self.factory.get('/api/consulta-ie/', {'cnpj': '00000000000191', 'uf': 'SP'})
        response = consulta_ie(request)
        self.assertEqual(response.status_code, 401)

    @patch('apps.cadastros.views.consultar_inscricao_estadual')
    def test_endpoint_autenticado(self, mock_consulta):
        mock_consulta.return_value = {
            'sucesso': True,
            'cnpj': '00000000000191',
            'uf': 'SP',
            'inscricao_estadual': '123456789012',
            'inscricoes_estaduais': [],
            'fonte': 'SEFAZ_NFE_CONSULTA_CADASTRO',
            'mensagem_usuario': 'ok',
        }
        request = self.factory.get('/api/consulta-ie/', {'cnpj': '00000000000191', 'uf': 'SP'})
        force_authenticate(request, user=self.user)
        response = consulta_ie(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['sucesso'])
