"""ERP 4.0.14.9.4 — Minha conta, nome exibido e cabeçalho refinado."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador, Empresa
from apps.core.app_contexto import montar_contexto_app, montar_minha_conta
from apps.core.prontidao_producao import verificar_usuarios_colaboradores

User = get_user_model()


class MinhaConta401494Tests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social='NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
            nome_fantasia='NEXUS VÁLVULAS',
            cnpj='12345678000199',
        )
        self.user = User.objects.create_superuser('admin401494', 'admin@localhost', 'Senha401494!')
        self.colaborador = Colaborador.objects.create(
            nome='BRUNO PRADO DE LIRA',
            codigo='B401494',
            email='admin@localhost',
            telefone='11999998888',
            usuario=self.user,
            ativo=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_contexto_nome_exibicao_colaborador(self):
        ctx = montar_contexto_app(self.user)
        self.assertEqual(ctx['usuario']['nome_exibicao'], 'BRUNO PRADO DE LIRA')
        self.assertEqual(ctx['usuario']['username'], 'admin401494')
        self.assertNotEqual(ctx['usuario']['nome_exibicao'], ctx['usuario']['username'])

    def test_contexto_fallback_username_sem_colaborador(self):
        user = User.objects.create_user('semcolab401494', 'sem401494@test.com', 'x')
        ctx = montar_contexto_app(user)
        self.assertEqual(ctx['usuario']['nome_exibicao'], 'semcolab401494')

    def test_minha_conta_nome_e_login_separados(self):
        r = self.client.get('/api/minha-conta/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['usuario']['nome_exibicao'], 'BRUNO PRADO DE LIRA')
        self.assertEqual(r.data['usuario']['username'], 'admin401494')

    def test_minha_conta_nao_retorna_senha(self):
        r = self.client.get('/api/minha-conta/')
        payload = str(r.data).lower()
        self.assertNotIn('password', payload)
        self.assertNotIn('senha', payload)

    def test_patch_email_valido(self):
        r = self.client.patch('/api/minha-conta/', {'email': 'bruno401494@test.com'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['usuario']['email'], 'bruno401494@test.com')
        self.assertIn('mensagem', r.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'bruno401494@test.com')

    def test_patch_email_invalido(self):
        r = self.client.patch('/api/minha-conta/', {'email': 'invalido'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_patch_email_duplicado(self):
        User.objects.create_user('outro401494', 'dup401494@test.com', 'x')
        r = self.client.patch('/api/minha-conta/', {'email': 'dup401494@test.com'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('e-mail', str(r.data).lower())

    def test_patch_nao_altera_perfil(self):
        g, _ = Group.objects.get_or_create(name='consulta')
        self.user.groups.add(g)
        r = self.client.patch(
            '/api/minha-conta/',
            {'email': 'bruno401494b@test.com', 'perfil': 'Administrador', 'groups': ['admin']},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.groups.filter(name='consulta').exists())

    def test_patch_nao_altera_login(self):
        r = self.client.patch(
            '/api/minha-conta/',
            {'email': 'bruno401494c@test.com', 'username': 'outrologin'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'admin401494')

    def test_minha_conta_aviso_email_tecnico(self):
        data = montar_minha_conta(self.user)
        self.assertTrue(data['usuario']['email_tecnico'])
        self.assertTrue(any('técnico' in a.lower() or 'local' in a.lower() for a in data['avisos']))

    def test_prontidao_email_tecnico_critico(self):
        achados, _ = verificar_usuarios_colaboradores()
        criticos = [a for a in achados if a.get('nivel') == 'critico']
        textos = ' '.join(a.get('mensagem', '') for a in criticos).lower()
        self.assertIn('técnico', textos)

    def test_contexto_empresa_razao_social_header(self):
        ctx = montar_contexto_app(self.user)
        self.assertEqual(
            ctx['empresa']['nome_exibicao'],
            'NEXUS VÁLVULAS E CONEXÕES INDUSTRIAIS LTDA',
        )
