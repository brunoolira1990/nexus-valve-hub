"""ERP 4.0.14.10.2 — gestão de perfil de acesso do usuário no colaborador."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.colaborador_acesso import AcessoStatus, montar_acesso_colaborador
from apps.cadastros.models import Colaborador
from apps.core.prontidao_producao import executar_verificacao_prontidao

User = get_user_model()
SENHA = 'SenhaSegura4014102!'


class ColaboradorAcesso4014102Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('adm4014102', 'admin@localhost', SENHA)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_superuser_sem_grupo_nao_critico_prontidao(self):
        c = Colaborador.objects.create(nome='Admin', codigo='ADM4102', usuario=self.admin, ativo=True)
        rel = executar_verificacao_prontidao()
        sem_perfil = [x for x in rel['criticos'] if 'sem perfil' in x['mensagem'].lower()]
        self.assertEqual(sem_perfil, [])
        self.assertEqual(montar_acesso_colaborador(c, actor=self.admin)['acesso_status'], AcessoStatus.SUPERUSUARIO)

    def test_usuario_ativo_sem_grupo_critico(self):
        user = User.objects.create_user('semg4102', 'semg4102@test.com', SENHA, is_active=True)
        Colaborador.objects.create(nome='Sem Grupo', codigo='SG4102', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(x['mensagem'] for x in rel['criticos']).lower()
        self.assertIn('sem perfil', msgs)
        self.assertIn('editar acesso', msgs)

    def test_usuario_com_grupo_nao_critico(self):
        Group.objects.get_or_create(name='financeiro')
        user = User.objects.create_user('fin4102', 'fin4102@test.com', SENHA, is_active=True)
        user.groups.add(Group.objects.get(name='financeiro'))
        Colaborador.objects.create(nome='Fin', codigo='FIN4102', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        sem_perfil = [x for x in rel['criticos'] if 'sem perfil' in x['mensagem'].lower()]
        self.assertEqual(sem_perfil, [])

    def test_email_local_critico_usuario_ativo(self):
        user = User.objects.create_user('loc4102', 'loc4102@localhost', SENHA, is_active=True)
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        Colaborador.objects.create(nome='Local', codigo='LOC4102', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(x['mensagem'] for x in rel['criticos']).lower()
        self.assertIn('técnico', msgs)

    def test_email_local_inativo_nao_critico(self):
        user = User.objects.create_user('inloc4102', 'inloc4102@localhost', SENHA, is_active=False)
        Colaborador.objects.create(nome='Inativo', codigo='INLOC4102', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        tecnico = [x for x in rel['criticos'] if 'técnico' in x['mensagem'].lower()]
        self.assertEqual(tecnico, [])

    def test_serializer_acesso_sistema_completo(self):
        c = Colaborador.objects.create(nome='Ser', codigo='S4102', usuario=self.admin, ativo=True)
        r = self.client.get(f'/api/colaboradores/{c.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('acesso_sistema', r.data)
        self.assertTrue(r.data['acesso_sistema']['tem_usuario'])
        self.assertTrue(r.data['pode_editar_acesso'])

    def test_patch_acesso_define_perfil(self):
        user = User.objects.create_user('patch4102', 'patch4102@test.com', SENHA, is_active=True)
        c = Colaborador.objects.create(nome='Patch', codigo='P4102', usuario=user, ativo=True)
        r = self.client.patch(
            f'/api/colaboradores/{c.pk}/acesso/',
            {'perfil': 'fiscal', 'ativo': True, 'email': 'patch4102@test.com'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.data)
        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name='fiscal').exists())

    def test_patch_bloqueia_ativo_sem_perfil(self):
        user = User.objects.create_user('bloq4102', 'bloq4102@test.com', SENHA, is_active=True)
        c = Colaborador.objects.create(nome='Bloq', codigo='B4102', usuario=user, ativo=True)
        r = self.client.patch(
            f'/api/colaboradores/{c.pk}/acesso/',
            {'ativo': True, 'email': 'bloq4102@test.com', 'perfil': ''},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('perfil', str(r.data).lower())

    def test_patch_bloqueia_email_tecnico_ativo(self):
        user = User.objects.create_user('tec4102', 'tec4102@test.com', SENHA, is_active=True)
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        c = Colaborador.objects.create(nome='Tec', codigo='T4102', usuario=user, ativo=True)
        r = self.client.patch(
            f'/api/colaboradores/{c.pk}/acesso/',
            {'email': 'tec4102@localhost', 'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_patch_bloqueia_email_duplicado(self):
        User.objects.create_user('dup4102', 'dup4102@test.com', SENHA, is_active=True)
        user = User.objects.create_user('out4102', 'out4102@test.com', SENHA, is_active=True)
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        c = Colaborador.objects.create(nome='Out', codigo='O4102', usuario=user, ativo=True)
        r = self.client.patch(
            f'/api/colaboradores/{c.pk}/acesso/',
            {'email': 'dup4102@test.com', 'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('e-mail', str(r.data).lower())

    def test_nao_desativa_proprio_usuario(self):
        c = Colaborador.objects.create(nome='Self', codigo='SELF4102', usuario=self.admin, ativo=True)
        r = self.client.post(f'/api/colaboradores/{c.pk}/desativar-acesso/', {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_nao_remove_ultimo_superuser(self):
        c = Colaborador.objects.create(nome='Only', codigo='ONLY4102', usuario=self.admin, ativo=True)
        r = self.client.patch(
            f'/api/colaboradores/{c.pk}/acesso/',
            {'is_superuser': False, 'perfil': 'administrador'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_criar_usuario_exige_perfil_se_ativo(self):
        c = Colaborador.objects.create(nome='Criar', codigo='C4102', email='criar4102@test.com', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {
                'email': 'criar4102@test.com',
                'nome': 'Criar',
                'perfil': '',
                'senha': SENHA,
                'confirmar_senha': SENHA,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_redefinir_senha_continua(self):
        user = User.objects.create_user('red4102', 'red4102@test.com', SENHA)
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        c = Colaborador.objects.create(nome='Red', codigo='R4102', usuario=user, ativo=True)
        nova = 'NovaSenha4014102!'
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/redefinir-senha/',
            {'nova_senha': nova, 'confirmar_senha': nova},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
