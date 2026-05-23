"""NF-e 3.6.1 — parser robusto e diagnóstico status serviço SEFAZ."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.test import TestCase
from lxml import etree
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSefazStatusConsulta
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import (
    CertificadoA1Error,
    validar_certificado_pfx,
)
from apps.fiscal.nfe_integracao.adapters.status_servico_parser import (
    normalizar_xml_bruto,
    parse_status_servico_response,
)
from apps.fiscal.nfe_integracao.adapters.tipos_erro import (
    TIPO_ERRO_CERTIFICADO,
    TIPO_ERRO_CONEXAO,
    TIPO_ERRO_PARSE,
    TIPO_ERRO_PYNFE,
)
from apps.fiscal.nfe_integracao.services import executar_status_servico

XML_NS = """<?xml version="1.0" encoding="UTF-8"?>
<retConsStatServ versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <tpAmb>2</tpAmb>
  <verAplic>SP_NFE_PL009_V4</verAplic>
  <cStat>107</cStat>
  <xMotivo>Servico em Operacao</xMotivo>
  <cUF>35</cUF>
</retConsStatServ>"""

XML_SEM_NS = """<?xml version="1.0"?>
<retConsStatServ versao="4.00">
  <cStat>108</cStat>
  <xMotivo>Servico Paralisado Momentaneamente</xMotivo>
</retConsStatServ>"""

XML_SOAP = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">
      <retConsStatServ versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
        <cStat>107</cStat>
        <xMotivo>OK SOAP</xMotivo>
      </retConsStatServ>
    </nfeResultMsg>
  </soap:Body>
</soap:Envelope>"""

XML_SEM_CSTAT = """<?xml version="1.0"?><retConsStatServ versao="4.00"><xMotivo>sem codigo</xMotivo></retConsStatServ>"""

XML_CSTAT_999 = """<?xml version="1.0"?><retConsStatServ versao="4.00"><cStat>999</cStat><xMotivo>Rejeicao teste</xMotivo></retConsStatServ>"""


def _criar_pfx_temp(senha: str = 'test123') -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, 'Empresa Teste LTDA 12345678000199'),
        ],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pfx = pkcs12.serialize_key_and_certificates(
        name=b'nexus-test',
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(senha.encode()),
    )
    tmp = tempfile.NamedTemporaryFile(suffix='.pfx', delete=False)
    tmp.write(pfx)
    tmp.flush()
    tmp.close()
    return tmp.name, senha


class StatusServicoParser361Tests(TestCase):
    def test_parse_xml_com_namespace(self):
        r = parse_status_servico_response(XML_NS)
        self.assertEqual(r['c_stat'], '107')
        self.assertEqual(r['x_motivo'], 'Servico em Operacao')
        self.assertFalse(r['erro_parse'])
        self.assertTrue(r['ok'])

    def test_parse_xml_sem_namespace(self):
        r = parse_status_servico_response(XML_SEM_NS)
        self.assertEqual(r['c_stat'], '108')
        self.assertFalse(r['erro_parse'])

    def test_parse_soap_envelope(self):
        r = parse_status_servico_response(XML_SOAP)
        self.assertEqual(r['c_stat'], '107')
        self.assertEqual(r['x_motivo'], 'OK SOAP')

    def test_parse_bytes(self):
        r = parse_status_servico_response(XML_NS.encode('utf-8'))
        self.assertEqual(r['c_stat'], '107')

    def test_parse_lxml_element(self):
        root = etree.fromstring(XML_NS.encode())
        r = parse_status_servico_response(root)
        self.assertEqual(r['c_stat'], '107')

    def test_parse_requests_like(self):
        resp = MagicMock()
        resp.text = XML_NS
        r = parse_status_servico_response(resp)
        self.assertEqual(r['c_stat'], '107')

    def test_resposta_vazia_parse_error(self):
        r = parse_status_servico_response('')
        self.assertTrue(r['erro_parse'])
        self.assertIn('vazia', r['motivo_erro'].lower())

    def test_xml_sem_cstat_parse_error(self):
        r = parse_status_servico_response(XML_SEM_CSTAT)
        self.assertTrue(r['erro_parse'])
        self.assertIn('cStat', r['motivo_erro'])

    def test_cstat_107_ok_true(self):
        r = parse_status_servico_response(XML_NS)
        self.assertTrue(r['ok'])
        self.assertTrue(r['servico_operacional'])

    def test_cstat_999_ok_false_preserva_campos(self):
        r = parse_status_servico_response(XML_CSTAT_999)
        self.assertFalse(r['ok'])
        self.assertEqual(r['c_stat'], '999')
        self.assertEqual(r['x_motivo'], 'Rejeicao teste')


class StatusServicoIntegracao361Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe361', 'nfe361@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pfx_path, self.pfx_pass = _criar_pfx_temp()
        self.empresa = Empresa.objects.create(
            razao_social='Emitente SP',
            cnpj='12345678000199',
            uf='SP',
            senha_certificado=self.pfx_pass,
        )
        with open(self.pfx_path, 'rb') as fh:
            self.empresa.certificado_arquivo.save('test.pfx', fh, save=True)

    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.status_servico_nfe')
    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.criar_comunicacao_sefaz')
    def test_executar_salva_motivo_em_falha_parse(self, mock_criar, mock_status):
        mock_status.return_value = MagicMock(text='<html><body>erro</body></html>')
        mock_criar.return_value = MagicMock()
        reg, res = executar_status_servico(self.empresa, homologacao=True)
        self.assertFalse(res.sucesso)
        self.assertTrue(reg.x_motivo)
        self.assertTrue(reg.erro_tecnico)
        self.assertEqual(reg.tipo_erro, TIPO_ERRO_PARSE)
        self.assertIsNotNone(reg.c_stat)
        self.assertEqual(reg.c_stat, '')

    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.status_servico_nfe')
    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.criar_comunicacao_sefaz')
    def test_pynfe_error_salva_erro_tecnico(self, mock_criar, mock_status):
        from apps.fiscal.nfe_integracao.adapters.exceptions import PyNFeComunicacaoError

        mock_criar.return_value = MagicMock()
        mock_status.side_effect = PyNFeComunicacaoError('timeout na SEFAZ')
        reg, res = executar_status_servico(self.empresa, homologacao=True)
        self.assertIn(res.tipo_erro, (TIPO_ERRO_PYNFE, TIPO_ERRO_CONEXAO))
        self.assertIn('timeout', reg.erro_tecnico.lower())
        self.assertTrue(reg.x_motivo)

    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.status_servico_nfe')
    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.criar_comunicacao_sefaz')
    def test_cstat_107_ok_api(self, mock_criar, mock_status):
        mock_status.return_value = MagicMock(text=XML_NS)
        mock_criar.return_value = MagicMock()
        res = self.client.post(
            '/api/nfe-sefaz-status/consultar/',
            {'empresa_id': self.empresa.pk, 'homologacao': True, 'uf': 'SP'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['ok'])
        self.assertEqual(res.data['cstat'], '107')
        self.assertIn('Operacao', res.data['motivo'])

    def test_charfield_nunca_null(self):
        reg = NFeSefazStatusConsulta.objects.create(
            empresa=self.empresa,
            uf='SP',
            ambiente='homologacao',
            c_stat='',
            x_motivo='Erro teste',
            erro_tecnico='detalhe',
            tipo_erro=TIPO_ERRO_PARSE,
        )
        self.assertEqual(reg.c_stat, '')
        self.assertEqual(reg.x_motivo, 'Erro teste')

    def test_historico_lista_erro_tecnico(self):
        NFeSefazStatusConsulta.objects.create(
            empresa=self.empresa,
            uf='SP',
            ambiente='homologacao',
            x_motivo='Falha parse',
            erro_tecnico='sem cStat',
            tipo_erro=TIPO_ERRO_PARSE,
        )
        res = self.client.get('/api/nfe-sefaz-status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data[0]['erro_tecnico'], 'sem cStat')

    def test_certificado_valido_retorna_datas(self):
        res = self.client.get(f'/api/empresas/{self.empresa.pk}/validar-certificado-nfe/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['valido'])
        self.assertIsNotNone(res.data['validade_fim'])
        self.assertIn('titular', res.data)

    def test_senha_errada_amigavel(self):
        with self.assertRaises(CertificadoA1Error) as ctx:
            validar_certificado_pfx(self.pfx_path, 'senha-errada')
        self.assertIn('Senha', str(ctx.exception))

    def test_resposta_nao_expoe_senha(self):
        with patch(
            'apps.fiscal.nfe_integracao.adapters.sefaz_status_service.status_servico_nfe',
        ) as mock_status:
            mock_status.return_value = MagicMock(text=XML_NS)
            with patch(
                'apps.fiscal.nfe_integracao.adapters.sefaz_status_service.criar_comunicacao_sefaz',
            ) as mock_criar:
                mock_criar.return_value = MagicMock()
                res = self.client.post(
                    '/api/nfe-sefaz-status/consultar/',
                    {'empresa_id': self.empresa.pk},
                    format='json',
                )
        body = str(res.data)
        self.assertNotIn(self.pfx_pass, body)
        self.assertNotIn('test123', body)

    def test_normalizar_xml_bruto_elementtree(self):
        from xml.etree import ElementTree as ET

        root = ET.fromstring(XML_NS)
        txt = normalizar_xml_bruto(root)
        self.assertIn('cStat', txt)
