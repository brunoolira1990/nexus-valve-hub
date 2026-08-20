import hashlib
import hmac
import json
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.crm.models import Lead


@override_settings(CRM_SITE_HMAC_SECRET='test-site-secret')
class SiteLeadCaptureTests(TestCase):
    def _post(self, payload, *, timestamp=None, signature=None, request_id=None):
        raw_body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(',', ':'),
        ).encode('utf-8')
        timestamp = str(timestamp if timestamp is not None else int(time.time()))
        request_id = request_id or payload['external_id']
        signature = signature or hmac.new(
            b'test-site-secret',
            f'{timestamp}.'.encode('utf-8') + raw_body,
            hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            reverse('crm-public-site-leads'),
            data=raw_body,
            content_type='application/json',
            HTTP_X_SITE_TIMESTAMP=timestamp,
            HTTP_X_SITE_REQUEST_ID=request_id,
            HTTP_X_SITE_SIGNATURE=signature,
        )

    def _payload(self, external_id='site-test-001'):
        return {
            'external_id': external_id,
            'nome': 'Bruno Lira',
            'empresa': 'Empresa de Homologação',
            'email': 'contato@example.com',
            'telefone': '(11) 99999-9999',
            'assunto': 'Solicitação de cotação',
            'mensagem': 'Preciso de válvula para uma aplicação industrial.',
            'produto_interesse': 'Válvula esfera',
            'pagina_origem': '/produtos/valvula-esfera',
            'utm_source': 'google',
            'utm_medium': 'cpc',
            'utm_campaign': 'teste-crm',
            'utm_content': 'anuncio-01',
            'utm_term': 'valvula industrial',
        }

    def test_cria_lead_site_com_atribuicao(self):
        response = self._post(self._payload())

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['duplicate'])
        lead = Lead.objects.get(external_id='site-test-001')
        self.assertEqual(lead.nome, 'Empresa de Homologação')
        self.assertEqual(lead.nome_contato, 'Bruno Lira')
        self.assertEqual(lead.origem, Lead.Origem.SITE)
        self.assertEqual(lead.status, Lead.Status.NOVO)
        self.assertEqual(lead.produto_interesse, 'Válvula esfera')
        self.assertEqual(lead.utm_campaign, 'teste-crm')
        self.assertIn('Preciso de válvula', lead.observacoes)

    def test_reenvio_do_mesmo_external_id_nao_duplica_lead(self):
        payload = self._payload('site-test-002')

        first = self._post(payload)
        second = self._post(payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['duplicate'])
        self.assertEqual(Lead.objects.filter(external_id='site-test-002').count(), 1)

    def test_rejeita_assinatura_invalida(self):
        response = self._post(self._payload('site-test-003'), signature='0' * 64)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Lead.objects.count(), 0)

    def test_rejeita_request_id_diferente_do_payload(self):
        response = self._post(
            self._payload('site-test-004'),
            request_id='outro-id',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Lead.objects.count(), 0)
