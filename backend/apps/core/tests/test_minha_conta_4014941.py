"""ERP 4.0.14.9.4.1 — nome exibido do colaborador no contexto/header."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador, Empresa
from django.test import TestCase

User = get_user_model()


class MinhaConta4014941Tests(TestCase):
    def setUp(self):
        Empresa.objects.create(
            razao_social='NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
            cnpj='12345678000199',
        )
        self.user = User.objects.create_superuser('admin', 'admin@localhost', 'Senha4014941!')
        self.colaborador = Colaborador.objects.create(
            nome='BRUNO PRADO DE LIRA',
            codigo='37869700843',
            usuario=self.user,
            ativo=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_contexto_nome_colaborador_vinculado(self):
        r = self.client.get('/api/app/contexto/')
        self.assertEqual(r.status_code, 200)
        u = r.data['usuario']
        self.assertEqual(u['nome_exibicao'], 'BRUNO PRADO DE LIRA')
        self.assertEqual(u['colaborador_nome'], 'BRUNO PRADO DE LIRA')
        self.assertEqual(u['username'], 'admin')
        self.assertNotEqual(u['nome_exibicao'], u['username'])

    def test_contexto_fallback_username_sem_colaborador(self):
        user = User.objects.create_user('isolado4014941', 'iso4014941@test.com', 'x')
        self.client.force_authenticate(user)
        r = self.client.get('/api/app/contexto/')
        self.assertEqual(r.data['usuario']['nome_exibicao'], 'isolado4014941')

    def test_minha_conta_nome_e_login_separados(self):
        r = self.client.get('/api/minha-conta/')
        self.assertEqual(r.data['usuario']['nome_exibicao'], 'BRUNO PRADO DE LIRA')
        self.assertEqual(r.data['usuario']['username'], 'admin')

    def test_api_nao_retorna_senha(self):
        r = self.client.get('/api/app/contexto/')
        payload = str(r.data).lower()
        self.assertNotIn('password', payload)
        self.assertNotIn('senha', payload)

    def test_superuser_com_colaborador(self):
        r = self.client.get('/api/app/contexto/')
        u = r.data['usuario']
        self.assertTrue(u['is_superuser'])
        self.assertEqual(u['perfil'], 'Superusuário')
        self.assertEqual(u['nome_exibicao'], 'BRUNO PRADO DE LIRA')
