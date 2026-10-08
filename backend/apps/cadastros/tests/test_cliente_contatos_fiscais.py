"""Contatos fiscais do Cliente — ativo, recebe_documentos_fiscais e unicidade de e-mail."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cadastros.contato_cliente_email import (
    MSG_EMAIL_DUPLICADO,
    MSG_EMAIL_FISCAL_OBRIGATORIO,
    MSG_EMAIL_INVALIDO,
)
from apps.cadastros.models import Cliente, ContatoCliente


class ClienteContatosFiscaisApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            'cliente_contatos_fiscais',
            'contatos_fiscais@test.local',
            'secret',
        )
        self.client.force_authenticate(user=user)

    def _payload_base(self, *, cnpj='11222333000181', razao='Cliente Contatos Fiscais'):
        return {
            'razao_social': razao,
            'nome_fantasia': '',
            'cnpj': cnpj,
            'ie': '',
            'ie_isento': False,
            'email': 'legado@test.local',
            'email_nf': 'nf-legado@test.local',
            'limite_credito': '0',
            'quantidade_parcelas': 0,
            'dias_parcelas': [],
            'bloqueado': False,
            'ativo': True,
        }

    def _contato(self, **overrides):
        base = {
            'tipo': 'COMERCIAL',
            'nome': 'CONTATO',
            'telefone': '',
            'celular': '',
            'email': 'contato@test.local',
            'principal': True,
            'ativo': True,
            'recebe_documentos_fiscais': False,
        }
        base.update(overrides)
        return base

    def test_criar_cliente_com_dois_contatos(self):
        payload = {
            **self._payload_base(),
            'contatos': [
                self._contato(tipo='FINANCEIRO', nome='A', email='a@test.local', principal=True),
                self._contato(tipo='COMERCIAL', nome='B', email='b@test.local', principal=True),
            ],
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data['contatos']), 2)
        for c in response.data['contatos']:
            self.assertIn('ativo', c)
            self.assertIn('recebe_documentos_fiscais', c)
            self.assertTrue(c['ativo'])
            self.assertFalse(c['recebe_documentos_fiscais'])

    def test_criar_multiplos_contatos_fiscais(self):
        payload = {
            **self._payload_base(),
            'contatos': [
                self._contato(
                    tipo='FINANCEIRO',
                    nome='FISCAL 1',
                    email='fiscal1@test.local',
                    recebe_documentos_fiscais=True,
                ),
                self._contato(
                    tipo='COMERCIAL',
                    nome='FISCAL 2',
                    email='fiscal2@test.local',
                    recebe_documentos_fiscais=True,
                ),
            ],
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        fiscais = [c for c in response.data['contatos'] if c['recebe_documentos_fiscais']]
        self.assertEqual(len(fiscais), 2)

    def test_contato_fiscal_sem_email_retorna_400(self):
        payload = {
            **self._payload_base(),
            'contatos': [
                self._contato(email='', recebe_documentos_fiscais=True),
            ],
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MSG_EMAIL_FISCAL_OBRIGATORIO, str(response.data))

    def test_email_invalido_retorna_400(self):
        payload = {
            **self._payload_base(),
            'contatos': [self._contato(email='nao-e-email')],
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MSG_EMAIL_INVALIDO, str(response.data))

    def test_duplicidade_no_payload_case_insensitive_retorna_400(self):
        payload = {
            **self._payload_base(),
            'contatos': [
                self._contato(tipo='FINANCEIRO', email='Duplicado@Test.Local', principal=True),
                self._contato(tipo='COMERCIAL', email='  duplicado@test.local ', principal=True),
            ],
        }
        response = self.client.post('/api/clientes/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MSG_EMAIL_DUPLICADO, str(response.data))

    def test_duplicidade_contra_contato_persistido_retorna_400(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [self._contato(email='persistido@test.local')],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        cliente_id = create.data['id']
        contato_id = create.data['contatos'][0]['id']

        response = self.client.patch(
            f'/api/clientes/{cliente_id}/',
            {
                'contatos': [
                    self._contato(id=contato_id, email='persistido@test.local'),
                    self._contato(
                        tipo='FINANCEIRO',
                        email='PERSISTIDO@test.local',
                        principal=True,
                    ),
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MSG_EMAIL_DUPLICADO, str(response.data))

    def test_atualizar_proprio_contato_sem_mudar_email(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [self._contato(nome='ORIGINAL', email='mesmo@test.local')],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        cliente_id = create.data['id']
        contato_id = create.data['contatos'][0]['id']

        response = self.client.patch(
            f'/api/clientes/{cliente_id}/',
            {
                'contatos': [
                    self._contato(
                        id=contato_id,
                        nome='ATUALIZADO',
                        email='mesmo@test.local',
                        recebe_documentos_fiscais=True,
                    ),
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['contatos'][0]['nome'], 'ATUALIZADO')
        self.assertTrue(response.data['contatos'][0]['recebe_documentos_fiscais'])

    def test_mesmo_email_em_clientes_diferentes_permitido(self):
        r1 = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(cnpj='11222333000181', razao='Cliente A'),
                'contatos': [self._contato(email='compartilhado@test.local')],
            },
            format='json',
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.data)
        r2 = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(cnpj='06990590000123', razao='Cliente B'),
                'contatos': [self._contato(email='compartilhado@test.local')],
            },
            format='json',
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.data)

    def test_contato_inativo_e_preservado(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [
                    self._contato(email='inativo@test.local', ativo=False),
                ],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        contato = create.data['contatos'][0]
        self.assertFalse(contato['ativo'])
        self.assertTrue(ContatoCliente.objects.filter(pk=contato['id'], ativo=False).exists())

    def test_omitir_contatos_em_patch_preserva(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [self._contato(email='manter@test.local')],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        cliente_id = create.data['id']
        contato_id = create.data['contatos'][0]['id']

        response = self.client.patch(
            f'/api/clientes/{cliente_id}/',
            {'nome_fantasia': 'FANTASIA SEM CONTATOS'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Cliente.objects.get(pk=cliente_id).contatos.count(), 1)
        self.assertTrue(ContatoCliente.objects.filter(pk=contato_id).exists())

    def test_contatos_lista_vazia_remove_todos(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [self._contato(email='remover@test.local')],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        cliente_id = create.data['id']

        response = self.client.patch(
            f'/api/clientes/{cliente_id}/',
            {'contatos': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Cliente.objects.get(pk=cliente_id).contatos.count(), 0)

    def test_campos_legados_email_permanecem_intactos(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [
                    self._contato(
                        email='extra@test.local',
                        recebe_documentos_fiscais=True,
                    ),
                ],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        self.assertEqual(create.data['email'], 'legado@test.local')
        self.assertEqual(create.data['email_nf'], 'nf-legado@test.local')

        cliente = Cliente.objects.get(pk=create.data['id'])
        self.assertEqual(cliente.email, 'legado@test.local')
        self.assertEqual(cliente.email_nf, 'nf-legado@test.local')

    def test_nao_autenticado_nao_altera_contatos(self):
        create = self.client.post(
            '/api/clientes/',
            {
                **self._payload_base(),
                'contatos': [self._contato(email='seguro@test.local')],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        cliente_id = create.data['id']

        self.client.force_authenticate(user=None)
        response = self.client.patch(
            f'/api/clientes/{cliente_id}/',
            {'contatos': []},
            format='json',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            response.data,
        )
        self.assertEqual(Cliente.objects.get(pk=cliente_id).contatos.count(), 1)
