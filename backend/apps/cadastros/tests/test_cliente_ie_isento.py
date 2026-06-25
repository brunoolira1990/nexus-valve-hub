"""API do campo ie_isento no cadastro de Cliente."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cadastros.models import Cliente


class ClienteIeIsentoApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('ie_isento_api', 'ie@test.local', 'secret')
        self.client.force_authenticate(user=user)

    def test_criar_cliente_com_ie_isento_limpa_ie(self):
        payload = {
            'razao_social': 'Cliente Isento API',
            'nome_fantasia': '',
            'cnpj': '11222333000181',
            'ie': '123456789',
            'ie_isento': True,
            'limite_credito': '0',
            'quantidade_parcelas': 0,
            'dias_parcelas': [],
            'bloqueado': False,
            'ativo': True,
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data['ie_isento'])
        self.assertEqual(response.data['ie'], '')

        cliente = Cliente.objects.get(pk=response.data['id'])
        self.assertTrue(cliente.ie_isento)
        self.assertEqual(cliente.ie, '')

    def test_atualizar_cliente_marca_ie_isento(self):
        cliente = Cliente.objects.create(
            razao_social='Cliente Update IE',
            cnpj='06990590000123',
            ie='ISENTO',
            uf='SP',
        )
        response = self.client.patch(
            f'/api/clientes/{cliente.pk}/',
            {'ie_isento': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ie_isento'])
        self.assertEqual(response.data['ie'], '')
