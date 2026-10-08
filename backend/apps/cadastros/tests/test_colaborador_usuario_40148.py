"""ERP 4.0.14.8 — usuário a partir de colaborador."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador

User = get_user_model()
SENHA = 'SenhaSegura40148!'


class ColaboradorUsuario40148Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('adm40148', 'adm40148@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_criar_usuario_a_partir_colaborador(self):
        c = Colaborador.objects.create(nome='Operador', codigo='OP40148', email='op40148@test.com', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {
                'email': 'op40148@test.com',
                'nome': 'Operador',
                'perfil': 'financeiro',
                'ativo': True,
                'senha': SENHA,
                'confirmar_senha': SENHA,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn('Usuário criado', r.data.get('mensagem', ''))
        self.assertEqual(r.data['acesso_status'], 'USUARIO_ATIVO')
        c.refresh_from_db()
        self.assertIsNotNone(c.usuario_id)

    def test_bloqueia_email_duplicado(self):
        User.objects.create_user('dup40148', 'dup40148@test.com', 'x')
        c = Colaborador.objects.create(nome='Dup', codigo='D40148', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {'email': 'dup40148@test.com', 'nome': 'Dup', 'perfil': 'consulta', 'senha': SENHA, 'confirmar_senha': SENHA},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('e-mail', str(r.data).lower())

    def test_bloqueia_dois_usuarios_mesmo_colaborador(self):
        c = Colaborador.objects.create(nome='Unico', codigo='U40148', ativo=True)
        r1 = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {'email': 'unico40148@test.com', 'nome': 'Unico', 'perfil': 'consulta', 'senha': SENHA, 'confirmar_senha': SENHA},
            format='json',
        )
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {'email': 'outro40148@test.com', 'nome': 'Unico', 'perfil': 'consulta', 'senha': SENHA, 'confirmar_senha': SENHA},
            format='json',
        )
        self.assertEqual(r2.status_code, 400)
        self.assertIn('já possui', str(r2.data).lower())

    def test_desativar_acesso_sem_apagar_colaborador(self):
        user = User.objects.create_user('des40148', 'des40148@test.com', 'x', is_active=True)
        c = Colaborador.objects.create(nome='Desativar', codigo='DES40148', usuario=user, ativo=True)
        r = self.client.post(f'/api/colaboradores/{c.pk}/desativar-acesso/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        user.refresh_from_db()
        self.assertTrue(c.ativo)
        self.assertFalse(user.is_active)
        self.assertEqual(r.data['acesso_status'], 'USUARIO_INATIVO')
