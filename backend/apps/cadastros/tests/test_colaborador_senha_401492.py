"""ERP 4.0.14.9.2 — senha inicial e redefinição por Admin."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador
from apps.core.prontidao_producao import executar_verificacao_prontidao

User = get_user_model()
SENHA = 'SenhaSegura401492!'


class ColaboradorSenha401492Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('adm401492', 'adm401492@test.com', SENHA)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.user_comum = User.objects.create_user('comum401492', 'comum401492@test.com', SENHA)
        Group.objects.get_or_create(name='consulta')
        self.user_comum.groups.add(Group.objects.get(name='consulta'))

    def _criar_payload(self, **overrides):
        base = {
            'email': 'novo401492@test.com',
            'nome': 'Novo Usuário',
            'perfil': 'financeiro',
            'ativo': True,
            'senha': SENHA,
            'confirmar_senha': SENHA,
        }
        base.update(overrides)
        return base

    def test_criar_usuario_com_senha_inicial(self):
        c = Colaborador.objects.create(nome='Novo', codigo='N401492', email='novo401492@test.com', ativo=True)
        r = self.client.post(f'/api/colaboradores/{c.pk}/criar-usuario/', self._criar_payload(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        c.refresh_from_db()
        self.assertTrue(c.usuario.check_password(SENHA))
        self.assertNotIn('password', str(r.data).lower())
        self.assertNotIn("'senha':", str(r.data).lower())

    def test_criar_usuario_exige_senha(self):
        c = Colaborador.objects.create(nome='S', codigo='S401492', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            self._criar_payload(senha='', confirmar_senha=''),
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_criar_usuario_bloqueia_senha_divergente(self):
        c = Colaborador.objects.create(nome='D', codigo='D401492', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            self._criar_payload(confirmar_senha='OutraSenha401492!'),
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('conferem', str(r.data).lower())

    def test_criar_usuario_bloqueia_email_invalido(self):
        c = Colaborador.objects.create(nome='E', codigo='E401492', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            self._criar_payload(email='comercial04@'),
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('e-mail válido', str(r.data).lower())

    def test_usuario_criado_senha_utilizavel(self):
        c = Colaborador.objects.create(nome='U', codigo='U401492', email='u401492@test.com', ativo=True)
        self.client.post(f'/api/colaboradores/{c.pk}/criar-usuario/', self._criar_payload(email='u401492@test.com'), format='json')
        c.refresh_from_db()
        self.assertTrue(is_password_usable(c.usuario.password))

    def test_admin_redefine_senha(self):
        user = User.objects.create_user('red401492', 'red401492@test.com', 'Antiga401492!')
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        c = Colaborador.objects.create(nome='Red', codigo='R401492', usuario=user, ativo=True)
        nova = 'NovaSenha401492!'
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/redefinir-senha/',
            {'nova_senha': nova, 'confirmar_senha': nova},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password(nova))
        self.assertFalse(user.check_password('Antiga401492!'))

    def test_usuario_comum_nao_redefine_senha_outro(self):
        alvo = User.objects.create_user('alvo401492', 'alvo401492@test.com', SENHA)
        c = Colaborador.objects.create(nome='Alvo', codigo='A401492', usuario=alvo, ativo=True)
        self.client.force_authenticate(self.user_comum)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/redefinir-senha/',
            {'nova_senha': 'Outra401492!', 'confirmar_senha': 'Outra401492!'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_alterar_senha_proprio_usuario(self):
        self.client.force_authenticate(self.user_comum)
        nova = 'MinhaNova401492!'
        r = self.client.post(
            '/api/minha-conta/alterar-senha/',
            {'senha_atual': SENHA, 'nova_senha': nova, 'confirmar_senha': nova},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.user_comum.refresh_from_db()
        self.assertTrue(self.user_comum.check_password(nova))

    def test_alterar_senha_senha_atual_incorreta(self):
        self.client.force_authenticate(self.user_comum)
        r = self.client.post(
            '/api/minha-conta/alterar-senha/',
            {'senha_atual': 'errada', 'nova_senha': 'Nova401492!', 'confirmar_senha': 'Nova401492!'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('incorreta', str(r.data).lower())

    def test_prontidao_acusa_sem_senha_utilizavel(self):
        user = User.objects.create_user('sem401492', 'sem401492@test.com', 'x')
        user.set_unusable_password()
        user.save()
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        Colaborador.objects.create(nome='Sem', codigo='SEM401492', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(x['mensagem'] for x in rel['criticos']).lower()
        self.assertIn('sem senha utilizável', msgs)

    def test_prontidao_ok_com_senha_e_perfil(self):
        user = User.objects.create_user('ok401492', 'ok401492@test.com', SENHA)
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        Colaborador.objects.create(nome='Ok', codigo='OK401492', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        sem_senha = [x for x in rel['criticos'] if 'sem senha utilizável' in x['mensagem'].lower()]
        sem_perfil = [x for x in rel['criticos'] if 'sem perfil' in x['mensagem'].lower()]
        self.assertEqual(len(sem_senha), 0)
        self.assertEqual(len(sem_perfil), 0)
