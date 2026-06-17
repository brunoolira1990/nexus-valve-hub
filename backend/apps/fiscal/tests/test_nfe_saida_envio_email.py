"""Envio manual DANFE/XML NF-e Saída por e-mail."""

from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.fiscal.models import NFeSaida, NFeSaidaEnvioEmail
from apps.fiscal.nfe_saida_envio_email import resolver_destinatario_email_cliente_nfe
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf, _preparar_pronta

XML_AUTORIZADO = '<?xml version="1.0"?><nfeProc><NFe/><protNFe/></nfeProc>'
PDF_MOCK = b'%PDF-1.4 mock'


class ResolverDestinatarioEmailClienteNfeTests(SimpleTestCase):
    def test_prioriza_email_nf(self):
        cliente = Mock()
        cliente.email_nf = 'fiscal@test.local'
        cliente.email = 'principal@test.local'
        nf = Mock(cliente_id=1, cliente=cliente)
        data = resolver_destinatario_email_cliente_nfe(nf)
        self.assertEqual(data['destinatario_sugerido'], 'fiscal@test.local')
        self.assertEqual(data['destinatario_origem'], 'email_nf')
        self.assertFalse(data['cliente_sem_email'])

    def test_usa_email_principal_sem_email_nf(self):
        cliente = Mock()
        cliente.email_nf = ''
        cliente.email = 'principal@test.local'
        nf = Mock(cliente_id=1, cliente=cliente)
        data = resolver_destinatario_email_cliente_nfe(nf)
        self.assertEqual(data['destinatario_sugerido'], 'principal@test.local')
        self.assertEqual(data['destinatario_origem'], 'email')

    def test_vazio_quando_cliente_sem_email(self):
        cliente = Mock()
        cliente.email_nf = ''
        cliente.email = ''
        nf = Mock(cliente_id=1, cliente=cliente)
        data = resolver_destinatario_email_cliente_nfe(nf)
        self.assertEqual(data['destinatario_sugerido'], '')
        self.assertTrue(data['cliente_sem_email'])


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='operacional@test.local',
    NEXUS_EMAIL_OPERACIONAL='operacional@test.local',
)
class NFeSaidaEnvioEmailTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('email_nfe', 'email@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        _pedido, _item, nf = _pedido_nf()
        self.nf = _preparar_pronta(nf, self.user)
        cliente = Cliente.objects.get(pk=self.nf.cliente_id)
        cliente.email_nf = 'cliente@test.local'
        cliente.save(update_fields=['email_nf'])
        self.nf.status = 'AUTORIZADA_HOMOLOGACAO'
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        self.nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
        self.nf.serie_nfe = '0'
        self.nf.numero_nfe = '000000099'
        self.nf.chave_acesso = '3526050399910200015055000000000991234567890'
        self.nf.protocolo_autorizacao = '135260000000099'
        self.nf.xml_autorizado = XML_AUTORIZADO
        self.nf.save()

    def _payload_envio(self, **extra):
        base = {
            'para': 'destino@test.local',
            'cc': '',
            'assunto': 'HOMOLOGAÇÃO — NF-e 99/0 — Sem valor fiscal',
            'mensagem': 'Documento emitido em ambiente de homologação, sem valor fiscal.',
            'confirmar_envio': True,
        }
        base.update(extra)
        return base

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_autorizada_com_xml_permite_envio(self, _mock_danfe):
        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertTrue(data['pode_enviar'])
        self.assertTrue(data['anexos']['xml_autorizado'])
        self.assertTrue(data['anexos']['danfe_pdf'])
        self.assertIn('HOMOLOG', data['alerta_homologacao'].upper())
        self.assertEqual(data['destinatario_sugerido'], 'cliente@test.local')
        self.assertEqual(data['destinatario_origem'], 'email_nf')
        self.assertFalse(data['cliente_sem_email'])
        self.assertEqual(data['aviso_sem_email_cliente'], '')

        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.json()['ok'])
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(len(msg.attachments), 2)
        self.assertEqual(NFeSaidaEnvioEmail.objects.filter(nfe_saida=self.nf).count(), 1)
        log = NFeSaidaEnvioEmail.objects.get(nfe_saida=self.nf)
        self.assertEqual(log.status_envio, NFeSaidaEnvioEmail.StatusEnvio.SUCESSO)

    def test_sem_xml_bloqueia_envio(self):
        self.nf.xml_autorizado = ''
        self.nf.save(update_fields=['xml_autorizado'])
        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        self.assertFalse(r.json()['pode_enviar'])
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelada_bloqueia_envio(self):
        self.nf.status = 'CANCELADA_HOMOLOGACAO'
        self.nf.save(update_fields=['status'])
        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        self.assertFalse(r.json()['pode_enviar'])
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_destinatario_sugerido_usa_email_principal_quando_sem_email_nf(self, _mock_danfe):
        cliente = Cliente.objects.get(pk=self.nf.cliente_id)
        cliente.email_nf = ''
        cliente.email = 'principal@test.local'
        cliente.save(update_fields=['email_nf', 'email'])

        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        data = r.json()
        self.assertEqual(data['destinatario_sugerido'], 'principal@test.local')
        self.assertEqual(data['destinatario_origem'], 'email')
        self.assertFalse(data['cliente_sem_email'])

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_destinatario_vazio_quando_cliente_sem_email(self, _mock_danfe):
        cliente = Cliente.objects.get(pk=self.nf.cliente_id)
        cliente.email_nf = ''
        cliente.email = ''
        cliente.save(update_fields=['email_nf', 'email'])

        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        data = r.json()
        self.assertEqual(data['destinatario_sugerido'], '')
        self.assertTrue(data['cliente_sem_email'])
        self.assertEqual(data['destinatario_origem'], '')
        self.assertIn('sem e-mail cadastrado', data['aviso_sem_email_cliente'].lower())

    def test_inutilizada_bloqueia_envio(self):
        self.nf.status = 'INUTILIZADA_HOMOLOGACAO'
        self.nf.save(update_fields=['status'])
        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        self.assertFalse(r.json()['pode_enviar'])

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_homologacao_exige_assunto_indicativo(self, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(assunto='NF-e 99/0 — Nexus'),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('HOMOLOG', res.json()['mensagem'].upper())

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_envio_nao_altera_status_fiscal_nem_xml(self, _mock_danfe):
        antes_status = self.nf.status
        antes_xml = self.nf.xml_autorizado
        antes_chave = self.nf.chave_acesso
        self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status, antes_status)
        self.assertEqual(self.nf.xml_autorizado, antes_xml)
        self.assertEqual(self.nf.chave_acesso, antes_chave)

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    @patch('apps.fiscal.nfe_saida_envio_email.EmailMessage.send', side_effect=ConnectionError('smtp down'))
    def test_erro_smtp_registra_falha_sem_vazar_secret(self, _mock_send, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('smtp down', res.json()['mensagem'].lower())
        self.assertIn('smtp', res.json()['mensagem'].lower())
        log = NFeSaidaEnvioEmail.objects.get(nfe_saida=self.nf)
        self.assertEqual(log.status_envio, NFeSaidaEnvioEmail.StatusEnvio.ERRO)
        self.assertNotIn('password', (log.mensagem_erro or '').lower())

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_exige_confirmacao_explicita(self, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(confirmar_envio=False),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
