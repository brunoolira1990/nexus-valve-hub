"""Envio manual DANFE/XML NF-e Saída por e-mail."""

from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, ContatoCliente
from apps.fiscal.models import NFeSaida, NFeSaidaEnvioEmail
from apps.fiscal.nfe_saida_envio_email import (
    montar_destinatarios_sugeridos,
    resolver_destinatario_email_cliente_nfe,
)
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import (
    XML_AUTORIZADO_MOCK,
    _pedido_nf,
    _preparar_pronta,
)

XML_AUTORIZADO = XML_AUTORIZADO_MOCK
PDF_MOCK = b'%PDF-1.4 mock'


class ResolverDestinatarioEmailClienteNfeTests(SimpleTestCase):
    def test_prioriza_email_nf(self):
        cliente = Mock()
        cliente.email_nf = 'fiscal@test.local'
        cliente.email = 'principal@test.local'
        cliente.contatos = Mock(all=Mock(return_value=[]))
        nf = Mock(cliente_id=1, cliente=cliente)
        data = resolver_destinatario_email_cliente_nfe(nf)
        self.assertEqual(data['destinatario_sugerido'], 'fiscal@test.local')
        self.assertEqual(data['destinatario_origem'], 'email_nf')
        self.assertFalse(data['cliente_sem_email'])

    def test_usa_email_principal_sem_email_nf(self):
        cliente = Mock()
        cliente.email_nf = ''
        cliente.email = 'principal@test.local'
        cliente.contatos = Mock(all=Mock(return_value=[]))
        nf = Mock(cliente_id=1, cliente=cliente)
        data = resolver_destinatario_email_cliente_nfe(nf)
        self.assertEqual(data['destinatario_sugerido'], 'principal@test.local')
        self.assertEqual(data['destinatario_origem'], 'email')

    def test_vazio_quando_cliente_sem_email(self):
        cliente = Mock()
        cliente.email_nf = ''
        cliente.email = ''
        cliente.contatos = Mock(all=Mock(return_value=[]))
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
        nf.ind_final = '1'
        nf.ind_pres = '1'
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
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
        self.assertTrue(any(d['email'] == 'cliente@test.local' for d in data['destinatarios_sugeridos']))

        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['destino@test.local'])
        self.assertEqual(len(mail.outbox[0].attachments), 2)
        self.assertEqual(NFeSaidaEnvioEmail.objects.filter(nfe_saida=self.nf).count(), 1)
        log = NFeSaidaEnvioEmail.objects.get(nfe_saida=self.nf)
        self.assertEqual(log.status_envio, NFeSaidaEnvioEmail.StatusEnvio.SUCESSO)
        self.assertEqual(log.destinatario, 'destino@test.local')

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
        self.assertEqual(data['destinatarios_sugeridos'], [])
        self.assertIn('destinatários fiscais', data['aviso_sem_email_cliente'].lower())

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
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        body = res.json()
        self.assertEqual(body['status_geral'], 'ERRO')
        self.assertFalse(body['ok'])
        self.assertNotIn('smtp down', body['mensagem'].lower())
        self.assertIn('smtp', body['mensagem'].lower())
        self.assertEqual(len(body.get('resultados') or []), 1)
        self.assertEqual(body['resultados'][0]['status'], 'ERRO')
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

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_dados_inclui_contatos_fiscais_ativos(self, _mock_danfe):
        cliente = Cliente.objects.get(pk=self.nf.cliente_id)
        ContatoCliente.objects.create(
            cliente=cliente,
            tipo=ContatoCliente.Tipo.FINANCEIRO,
            nome='FISCAL ATIVO',
            email='contato-fiscal@test.local',
            principal=True,
            ativo=True,
            recebe_documentos_fiscais=True,
        )
        ContatoCliente.objects.create(
            cliente=cliente,
            tipo=ContatoCliente.Tipo.COMERCIAL,
            nome='INATIVO',
            email='inativo@test.local',
            principal=True,
            ativo=False,
            recebe_documentos_fiscais=True,
        )
        ContatoCliente.objects.create(
            cliente=cliente,
            tipo=ContatoCliente.Tipo.TECNICO,
            nome='SEM FLAG',
            email='sem-flag@test.local',
            principal=True,
            ativo=True,
            recebe_documentos_fiscais=False,
        )

        r = self.client.get(f'/api/nf-saidas/{self.nf.pk}/envio-email/dados/')
        data = r.json()
        emails = [d['email'] for d in data['destinatarios_sugeridos']]
        self.assertIn('contato-fiscal@test.local', emails)
        self.assertIn('cliente@test.local', emails)
        self.assertNotIn('inativo@test.local', emails)
        self.assertNotIn('sem-flag@test.local', emails)
        fiscal = next(
            d for d in data['destinatarios_sugeridos'] if d['email'] == 'contato-fiscal@test.local'
        )
        self.assertEqual(fiscal['origem'], 'contato')
        self.assertTrue(fiscal['selecionado'])

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_envio_multiplo_um_email_por_destinatario(self, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(
                destinatarios=['a@test.local', 'b@test.local', 'A@test.local'],
                para='',
            ),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())
        body = res.json()
        self.assertEqual(body['status_geral'], 'SUCESSO')
        self.assertTrue(body['ok'])
        self.assertEqual(body['total'], 2)
        self.assertEqual(body['sucessos'], 2)
        self.assertEqual(body['falhas'], 0)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['a@test.local'])
        self.assertEqual(mail.outbox[1].to, ['b@test.local'])
        self.assertEqual(len(mail.outbox[0].to), 1)
        self.assertFalse(mail.outbox[0].cc)
        self.assertEqual(NFeSaidaEnvioEmail.objects.filter(nfe_saida=self.nf).count(), 2)
        self.assertEqual(len(body['resultados']), 2)

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_envio_parcial_registra_sucesso_e_erro(self, _mock_danfe):
        calls = {'n': 0}

        def _send_side_effect(self_msg, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 2:
                raise ConnectionError('smtp down')
            return 1

        with patch(
            'apps.fiscal.nfe_saida_envio_email.EmailMessage.send',
            autospec=True,
            side_effect=_send_side_effect,
        ):
            res = self.client.post(
                f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
                self._payload_envio(destinatarios=['ok@test.local', 'fail@test.local'], para=''),
                format='json',
            )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())
        body = res.json()
        self.assertEqual(body['status_geral'], 'PARCIAL')
        self.assertTrue(body['ok'])
        self.assertEqual(body['sucessos'], 1)
        self.assertEqual(body['falhas'], 1)
        self.assertIn('parcial', body['mensagem'].lower())
        statuses = {r['email']: r['status'] for r in body['resultados']}
        self.assertEqual(statuses['ok@test.local'], 'SUCESSO')
        self.assertEqual(statuses['fail@test.local'], 'ERRO')
        self.assertEqual(NFeSaidaEnvioEmail.objects.filter(nfe_saida=self.nf).count(), 2)

    def test_montar_destinatarios_dedupe_case_insensitive(self):
        cliente = Cliente.objects.get(pk=self.nf.cliente_id)
        cliente.email_nf = 'Mesmo@test.local'
        cliente.email = 'mesmo@test.local'
        cliente.save(update_fields=['email_nf', 'email'])
        ContatoCliente.objects.create(
            cliente=cliente,
            tipo=ContatoCliente.Tipo.FINANCEIRO,
            nome='DUP',
            email='MESMO@test.local',
            principal=True,
            ativo=True,
            recebe_documentos_fiscais=True,
        )
        self.nf.refresh_from_db()
        itens = montar_destinatarios_sugeridos(self.nf)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]['origem'], 'contato')

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_cc_legado_com_um_destinatario(self, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(para='unico@test.local', cc='copia@test.local'),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())
        self.assertEqual(res.json()['status_geral'], 'SUCESSO')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['unico@test.local'])
        self.assertEqual(mail.outbox[0].cc, ['copia@test.local'])
        log = NFeSaidaEnvioEmail.objects.get(nfe_saida=self.nf)
        self.assertIn('copia@test.local', log.copias)

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    @patch('apps.fiscal.nfe_saida_envio_email.EmailMessage.send')
    def test_cc_com_multiplos_destinatarios_retorna_400_sem_smtp(self, mock_send, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(
                destinatarios=['a@test.local', 'b@test.local'],
                para='',
                cc='copia@test.local',
            ),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('CC', res.json()['mensagem'])
        mock_send.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NFeSaidaEnvioEmail.objects.filter(nfe_saida=self.nf).count(), 0)

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_para_legado_sozinho(self, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(para='legado@test.local'),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()['status_geral'], 'SUCESSO')
        self.assertEqual(mail.outbox[0].to, ['legado@test.local'])

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_destinatarios_sozinho(self, _mock_danfe):
        payload = self._payload_envio(destinatarios=['novo@test.local'], para='')
        payload.pop('para', None)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            payload,
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())
        self.assertEqual(mail.outbox[0].to, ['novo@test.local'])

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_para_e_destinatarios_equivalentes_nao_duplicam(self, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(
                para='A@test.local, b@test.local',
                destinatarios=['a@test.local', 'B@test.local'],
            ),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.json())
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(res.json()['total'], 2)

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    @patch('apps.fiscal.nfe_saida_envio_email.EmailMessage.send')
    def test_para_e_destinatarios_conflitantes_retorna_400(self, mock_send, _mock_danfe):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(
                para='a@test.local',
                destinatarios=['b@test.local'],
            ),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('conflito', res.json()['mensagem'].lower())
        mock_send.assert_not_called()

    @patch('apps.fiscal.nfe_saida_envio_email.resolver_xml_autorizado_danfe', return_value=XML_AUTORIZADO)
    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_anexos_gerados_uma_unica_vez_por_requisicao(self, mock_danfe, mock_xml):
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(destinatarios=['a@test.local', 'b@test.local'], para=''),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # DANFE gerado uma vez; XML resolvido na avaliação + uma vez no envio (não por destinatário).
        self.assertEqual(mock_danfe.call_count, 1)
        self.assertLessEqual(mock_xml.call_count, 3)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(len(mail.outbox[0].attachments), 2)
        self.assertEqual(len(mail.outbox[1].attachments), 2)
        # Mesmos bytes reutilizados (conteúdo idêntico nos dois envios).
        self.assertEqual(mail.outbox[0].attachments[0][1], mail.outbox[1].attachments[0][1])
        self.assertEqual(mail.outbox[0].attachments[1][1], mail.outbox[1].attachments[1][1])

    @patch('apps.fiscal.nfe_saida_envio_email.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {}))
    def test_falha_no_primeiro_nao_impede_sucesso_no_segundo(self, _mock_danfe):
        calls = {'n': 0}

        def _send_side_effect(self_msg, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 1:
                raise ConnectionError('smtp down')
            return 1

        with patch(
            'apps.fiscal.nfe_saida_envio_email.EmailMessage.send',
            autospec=True,
            side_effect=_send_side_effect,
        ):
            res = self.client.post(
                f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
                self._payload_envio(destinatarios=['fail@test.local', 'ok@test.local'], para=''),
                format='json',
            )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertEqual(body['status_geral'], 'PARCIAL')
        statuses = {r['email']: r['status'] for r in body['resultados']}
        self.assertEqual(statuses['fail@test.local'], 'ERRO')
        self.assertEqual(statuses['ok@test.local'], 'SUCESSO')

    def test_nao_autenticado_retorna_401(self):
        self.client.force_authenticate(user=None)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/envio-email/enviar/',
            self._payload_envio(),
            format='json',
        )
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
