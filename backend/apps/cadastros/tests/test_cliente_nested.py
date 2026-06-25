"""API nested — endereços de entrega e contatos do cliente."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cadastros.models import Cliente, ContatoCliente, EnderecoEntregaCliente


class ClienteNestedApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('cliente_nested', 'nested@test.local', 'secret')
        self.client.force_authenticate(user=user)

    def _payload_base(self):
        return {
            'razao_social': 'Cliente Nested',
            'nome_fantasia': '',
            'cnpj': '11222333000181',
            'ie': '',
            'ie_isento': False,
            'limite_credito': '0',
            'quantidade_parcelas': 0,
            'dias_parcelas': [],
            'bloqueado': False,
            'ativo': True,
        }

    def test_criar_cliente_com_enderecos_entrega_e_contatos(self):
        payload = {
            **self._payload_base(),
            'enderecos_entrega': [
                {
                    'identificacao': 'FILIAL CAMPINAS',
                    'cep': '13010000',
                    'logradouro': 'RUA TESTE',
                    'numero': '100',
                    'complemento': '',
                    'bairro': 'CENTRO',
                    'cidade': 'CAMPINAS',
                    'uf': 'SP',
                    'principal': True,
                }
            ],
            'contatos': [
                {
                    'tipo': 'FINANCEIRO',
                    'nome': 'MARIA FINANCEIRO',
                    'telefone': '19999999999',
                    'celular': '',
                    'email': 'financeiro@test.local',
                    'principal': True,
                },
                {
                    'tipo': 'COMERCIAL',
                    'nome': 'JOAO COMERCIAL',
                    'telefone': '',
                    'celular': '19988887777',
                    'email': 'comercial@test.local',
                    'principal': True,
                },
            ],
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        cliente_id = response.data['id']
        self.assertEqual(len(response.data['enderecos_entrega']), 1)
        self.assertEqual(len(response.data['contatos']), 2)

        cliente = Cliente.objects.get(pk=cliente_id)
        self.assertEqual(cliente.enderecos_entrega.count(), 1)
        endereco = cliente.enderecos_entrega.get()
        self.assertEqual(endereco.identificacao, 'FILIAL CAMPINAS')
        self.assertTrue(endereco.principal)

        financeiro = cliente.contatos.get(tipo=ContatoCliente.Tipo.FINANCEIRO)
        self.assertEqual(financeiro.nome, 'MARIA FINANCEIRO')
        self.assertTrue(financeiro.principal)

    def test_atualizar_remove_endereco_e_contato(self):
        cliente = Cliente.objects.create(razao_social='Cliente Sync', cnpj='06990590000123', uf='SP')
        endereco = EnderecoEntregaCliente.objects.create(
            cliente=cliente,
            identificacao='DEPOSITO',
            cidade='SAO PAULO',
            uf='SP',
            principal=True,
        )
        contato = ContatoCliente.objects.create(
            cliente=cliente,
            tipo=ContatoCliente.Tipo.TECNICO,
            nome='TECNICO ANTIGO',
            principal=True,
        )

        response = self.client.patch(
            f'/api/clientes/{cliente.pk}/',
            {
                'enderecos_entrega': [
                    {
                        'id': endereco.pk,
                        'identificacao': 'DEPOSITO ATUALIZADO',
                        'cep': '',
                        'logradouro': '',
                        'numero': '',
                        'complemento': '',
                        'bairro': '',
                        'cidade': 'SAO PAULO',
                        'uf': 'SP',
                        'principal': True,
                    }
                ],
                'contatos': [],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(cliente.enderecos_entrega.count(), 1)
        endereco.refresh_from_db()
        self.assertEqual(endereco.identificacao, 'DEPOSITO ATUALIZADO')
        self.assertFalse(ContatoCliente.objects.filter(pk=contato.pk).exists())
