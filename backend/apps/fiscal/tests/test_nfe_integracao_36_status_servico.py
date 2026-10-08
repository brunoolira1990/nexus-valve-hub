"""NF-e 3.6 — certificado A1 e status serviço SEFAZ (mock PyNFe)."""

from __future__ import annotations

import tempfile
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSefazStatusConsulta
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import validar_certificado_pfx
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import parse_ret_cons_stat_serv
from apps.fiscal.nfe_integracao.services import executar_status_servico


def _criar_pfx_temp(senha: str = 'test123') -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, 'Empresa Teste LTDA 12345678000199'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Empresa Teste'),
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


XML_STATUS_OK = """<?xml version="1.0" encoding="UTF-8"?>
<retConsStatServ versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <tpAmb>2</tpAmb>
  <verAplic>SP_NFE_PL009_V4</verAplic>
  <cStat>107</cStat>
  <xMotivo>Servico em Operacao</xMotivo>
  <cUF>35</cUF>
  <dhRecbto>2026-05-21T10:00:00-03:00</dhRecbto>
  <tMed>1</tMed>
</retConsStatServ>"""


class NFeIntegracao36Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe36', 'nfe36@test.com', 'x')
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

    def test_validar_certificado_pfx(self):
        info = validar_certificado_pfx(self.pfx_path, self.pfx_pass)
        self.assertTrue(info.valido)
        self.assertIsNotNone(info.validade_fim)

    def test_parse_ret_cons_stat_serv(self):
        parsed = parse_ret_cons_stat_serv(XML_STATUS_OK)
        self.assertEqual(parsed.c_stat, '107')
        self.assertTrue(parsed.servico_operacional)

    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.status_servico_nfe')
    @patch('apps.fiscal.nfe_integracao.adapters.sefaz_status_service.criar_comunicacao_sefaz')
    def test_executar_status_servico_mock(self, mock_criar, mock_status):
        mock_resp = MagicMock()
        mock_resp.text = XML_STATUS_OK
        mock_status.return_value = mock_resp
        mock_criar.return_value = MagicMock()

        reg, res = executar_status_servico(self.empresa, homologacao=True, usuario=self.user)
        self.assertTrue(res.sucesso)
        self.assertEqual(res.retorno.c_stat, '107')
        self.assertEqual(reg.c_stat, '107')
        self.assertTrue(reg.servico_operacional)
        self.assertIn('SP', reg.uf)

    @patch('apps.fiscal.nfe_integracao.services.consultar_status_servico_empresa')
    def test_api_consultar_status(self, mock_consulta):
        from apps.fiscal.nfe_integracao.adapters.sefaz_status_service import ResultadoStatusServico
        from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import RetornoStatusServicoParsed
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import CertificadoA1Info

        mock_consulta.return_value = ResultadoStatusServico(
            sucesso=True,
            uf='SP',
            ambiente='homologacao',
            modelo='nfe',
            certificado=CertificadoA1Info(valido=True, caminho=self.pfx_path, senha_configurada=True),
            retorno=RetornoStatusServicoParsed(
                c_stat='107',
                x_motivo='Servico em Operacao',
                servico_operacional=True,
            ),
            xml_resposta=XML_STATUS_OK,
            mensagens=['OK'],
        )
        res = self.client.post(
            '/api/nfe-sefaz-status/consultar/',
            {'empresa_id': self.empresa.pk, 'homologacao': True, 'uf': 'SP'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data.get('ok') or res.data.get('c_stat') == '107')
        self.assertEqual(res.data.get('cstat') or res.data.get('c_stat'), '107')
        self.assertEqual(NFeSefazStatusConsulta.objects.filter(empresa=self.empresa).count(), 1)

    def test_api_validar_certificado_empresa(self):
        res = self.client.get(f'/api/empresas/{self.empresa.pk}/validar-certificado-nfe/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['valido'])

    def test_list_historico_status(self):
        NFeSefazStatusConsulta.objects.create(
            empresa=self.empresa,
            uf='SP',
            ambiente='homologacao',
            sucesso=True,
            c_stat='107',
            x_motivo='OK',
            servico_operacional=True,
        )
        res = self.client.get('/api/nfe-sefaz-status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)
