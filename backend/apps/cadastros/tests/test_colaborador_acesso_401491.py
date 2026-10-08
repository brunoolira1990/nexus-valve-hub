"""ERP 4.0.14.9.1 — acesso ao sistema via colaborador."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.colaborador_acesso import AcessoStatus, montar_acesso_colaborador
from apps.cadastros.models import Colaborador
from apps.core.prontidao_producao import executar_verificacao_prontidao

User = get_user_model()
SENHA = 'SenhaSegura401491!'


class ColaboradorAcesso401491Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('adm401491', 'adm401491@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_criar_usuario_exige_email(self):
        c = Colaborador.objects.create(nome='Sem Email', codigo='SE401491', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {'email': '', 'perfil': 'financeiro'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_criar_usuario_exige_perfil(self):
        c = Colaborador.objects.create(nome='Sem Perfil', codigo='SP401491', email='sp@test.com', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {'email': 'sp@test.com', 'nome': 'Sem Perfil', 'perfil': ''},
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_criar_usuario_adiciona_group(self):
        c = Colaborador.objects.create(
            nome='Fin',
            codigo='FIN401491',
            email='fin401491@test.com',
            eh_responsavel_financeiro=True,
            ativo=True,
        )
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {
                'email': 'fin401491@test.com',
                'nome': 'Fin',
                'perfil': 'financeiro',
                'senha': SENHA,
                'confirmar_senha': SENHA,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['acesso_status'], AcessoStatus.USUARIO_ATIVO)
        self.assertEqual(r.data['perfil_acesso'], 'financeiro')
        c.refresh_from_db()
        self.assertTrue(c.usuario.groups.filter(name='financeiro').exists())

    def test_bloqueia_email_duplicado_amigavel(self):
        User.objects.create_user('dup401491', 'dup401491@test.com', 'x')
        c = Colaborador.objects.create(nome='Dup', codigo='D401491', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/criar-usuario/',
            {
                'email': 'dup401491@test.com',
                'nome': 'Dup',
                'perfil': 'consulta',
                'senha': SENHA,
                'confirmar_senha': SENHA,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('e-mail', str(r.data).lower())

    def test_vincular_usuario_sem_perfil_exige_perfil(self):
        user = User.objects.create_user('vinc401491', 'vinc401491@test.com', 'x')
        c = Colaborador.objects.create(nome='Vinc', codigo='V401491', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/vincular-usuario/',
            {'usuario_id': user.pk},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('perfil', str(r.data).lower())

    def test_vincular_usuario_com_perfil(self):
        Group.objects.get_or_create(name='comercial')
        user = User.objects.create_user('vinc2401491', 'vinc2401491@test.com', 'x')
        c = Colaborador.objects.create(nome='Vinc2', codigo='V2401491', ativo=True)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/vincular-usuario/',
            {'usuario_id': user.pk, 'perfil': 'comercial'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('vinculado', r.data.get('mensagem', '').lower())
        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name='comercial').exists())

    def test_definir_perfil_acesso(self):
        user = User.objects.create_user('semg401491', 'semg401491@test.com', 'x', is_active=True)
        c = Colaborador.objects.create(nome='Sem Grupo', codigo='SG401491', usuario=user, ativo=True)
        self.assertEqual(montar_acesso_colaborador(c)['acesso_status'], AcessoStatus.SEM_PERFIL)
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/definir-perfil-acesso/',
            {'perfil': 'fiscal'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['acesso_status'], AcessoStatus.USUARIO_ATIVO)
        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name='fiscal').exists())

    def test_prontidao_acusa_sem_perfil(self):
        user = User.objects.create_user('pront401491', 'pront401491@test.com', 'x', is_active=True)
        Colaborador.objects.create(nome='Pront', codigo='PR401491', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        msgs = ' '.join(x['mensagem'] for x in rel['criticos']).lower()
        self.assertIn('sem perfil', msgs)

    def test_prontidao_ok_apos_definir_perfil(self):
        Group.objects.get_or_create(name='consulta')
        user = User.objects.create_user('ok401491', 'ok401491@test.com', 'x', is_active=True)
        user.groups.add(Group.objects.get(name='consulta'))
        Colaborador.objects.create(nome='Ok', codigo='OK401491', usuario=user, ativo=True)
        rel = executar_verificacao_prontidao()
        sem_perfil_msgs = [x for x in rel['criticos'] if 'sem perfil' in x['mensagem'].lower()]
        self.assertEqual(len(sem_perfil_msgs), 0)

    def test_serializer_acesso_status(self):
        c = Colaborador.objects.create(nome='Ser', codigo='S401491', ativo=True)
        r = self.client.get(f'/api/colaboradores/{c.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['acesso_status'], AcessoStatus.SEM_USUARIO)
        self.assertTrue(r.data['pode_criar_usuario'])

    def test_admin_pode_redefinir_senha(self):
        user = User.objects.create_user('red401491', 'red401491@test.com', SENHA)
        c = Colaborador.objects.create(
            nome='Red',
            codigo='R401491',
            email='red401491@test.com',
            usuario=user,
            ativo=True,
        )
        Group.objects.get_or_create(name='consulta')
        user.groups.add(Group.objects.get(name='consulta'))
        nova = 'NovaSenha401491!'
        r = self.client.post(
            f'/api/colaboradores/{c.pk}/redefinir-senha/',
            {'nova_senha': nova, 'confirmar_senha': nova},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('password', str(r.data).lower())
        self.assertNotIn("'senha':", str(r.data).lower())
