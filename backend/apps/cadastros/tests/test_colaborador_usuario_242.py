"""Comercial/Cadastros 2.4.2 — vínculo Colaborador ↔ User e API de usuários."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador
from apps.cadastros.colaborador_sync import sincronizar_vendedor_colaborador
from apps.comercial.models import Vendedor

User = get_user_model()


class ColaboradorUsuario242Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('auth242', 'auth242@test.com', 'secret-pass')
        self.other = User.objects.create_user('other242', 'other242@test.com', 'secret-pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_listar_usuarios_ativos(self):
        User.objects.create_user('inativo242', 'inativo@test.com', 'x', is_active=False)
        r = self.client.get('/api/usuarios/')
        self.assertEqual(r.status_code, 200)
        usernames = [x['username'] for x in r.data]
        self.assertIn('auth242', usernames)
        self.assertIn('other242', usernames)
        self.assertNotIn('inativo242', usernames)

    def test_buscar_usuario_por_email(self):
        r = self.client.get('/api/usuarios/', {'search': 'other242@test'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['username'], 'other242')

    def test_usuarios_nao_expoe_senha(self):
        r = self.client.get('/api/usuarios/')
        self.assertEqual(r.status_code, 200)
        for row in r.data:
            self.assertNotIn('password', row)
            self.assertNotIn('password', str(row).lower())
            self.assertEqual(set(row.keys()), {'id', 'username', 'email', 'first_name', 'last_name', 'is_active'})

    def test_vincular_usuario_colaborador(self):
        c = Colaborador.objects.create(nome='Vincular', codigo='V242', ativo=True)
        r = self.client.patch(f'/api/colaboradores/{c.pk}/', {'usuario_id': self.other.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['usuario_id'], self.other.pk)
        self.assertEqual(r.data['usuario_login'], 'other242')
        c.refresh_from_db()
        self.assertEqual(c.usuario_id, self.other.pk)

    def test_desvincular_usuario_colaborador(self):
        c = Colaborador.objects.create(nome='Desv', codigo='D242', usuario=self.other, ativo=True)
        r = self.client.patch(f'/api/colaboradores/{c.pk}/', {'usuario_id': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['usuario_id'])
        c.refresh_from_db()
        self.assertIsNone(c.usuario_id)

    def test_bloquear_usuario_em_dois_colaboradores_ativos(self):
        Colaborador.objects.create(nome='Primeiro', codigo='P1', usuario=self.other, ativo=True)
        c2 = Colaborador.objects.create(nome='Segundo', codigo='P2', ativo=True)
        r = self.client.patch(f'/api/colaboradores/{c2.pk}/', {'usuario_id': self.other.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('usuario_id', r.data)
        msg = str(r.data['usuario_id'])
        self.assertIn('já está vinculado', msg)
        self.assertIn('Primeiro', msg)

    def test_colaborador_vinculado_endpoint(self):
        Colaborador.objects.create(
            nome='Meu',
            codigo='M242',
            usuario=self.user,
            eh_vendedor=True,
            ativo=True,
        )
        r = self.client.get('/api/colaboradores/vinculado/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['codigo'], 'M242')

    def test_default_vendedor_proposta_apos_vinculo(self):
        from datetime import date

        from apps.cadastros.models import Cliente, Empresa
        from apps.comercial.tests.test_comercial_vendedor_232 import _cnpj

        c = Colaborador.objects.create(
            nome='Vend Default',
            codigo='VD242',
            usuario=self.user,
            eh_vendedor=True,
            ativo=True,
        )
        sincronizar_vendedor_colaborador(c)
        emp = Empresa.objects.create(razao_social='E VD', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='C VD', cnpj=_cnpj())
        hoje = date.today().isoformat()
        r = self.client.post(
            '/api/propostas/',
            {
                'data': hoje,
                'validade': hoje,
                'cliente_id': cli.pk,
                'empresa_emitente_id': emp.pk,
                'status': 'PENDENTE',
                'condicao_pagamento_texto': '30',
                'itens': [],
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNotNone(r.data.get('vendedor_id'))
        v = Vendedor.objects.get(pk=r.data['vendedor_id'])
        self.assertEqual(v.colaborador_id, c.pk)

    def test_vendedor_sync_copia_usuario(self):
        c = Colaborador.objects.create(
            nome='Sync U',
            codigo='SU242',
            usuario=self.other,
            eh_vendedor=True,
            ativo=True,
        )
        v = Vendedor.objects.filter(colaborador=c).first()
        self.assertIsNotNone(v)
        self.assertEqual(v.usuario_id, self.other.pk)
        r = self.client.patch(f'/api/colaboradores/{c.pk}/', {'usuario_id': self.user.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        v.refresh_from_db()
        self.assertEqual(v.usuario_id, self.user.pk)

    def test_listagem_colaborador_usuario_email(self):
        Colaborador.objects.create(nome='E-mail', codigo='EM242', usuario=self.other, ativo=True)
        r = self.client.get('/api/colaboradores/')
        row = next(x for x in r.data if x['codigo'] == 'EM242')
        self.assertEqual(row['usuario_email'], 'other242@test.com')
