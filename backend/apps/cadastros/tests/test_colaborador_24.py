"""Comercial/Cadastros 2.4 — colaboradores e vínculo com vendedor."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador
from apps.comercial.models import Vendedor

User = get_user_model()


class Colaborador24Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('colab24', 'c24@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_criar_e_buscar_colaborador(self):
        r = self.client.post(
            '/api/colaboradores/',
            {
                'nome': 'Ana Vendedora',
                'codigo': 'AV',
                'email': 'ana@ex.com',
                'eh_vendedor': True,
                'ativo': True,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        cid = r.data['id']
        self.assertTrue(r.data['vendedor_id'])
        r2 = self.client.get('/api/colaboradores/', {'search': 'ana'})
        ids = [x['id'] for x in (r2.data if isinstance(r2.data, list) else r2.data.get('results', []))]
        self.assertIn(cid, ids)

    def test_filtrar_por_funcao_vendedor(self):
        Colaborador.objects.create(nome='V1', codigo='V1', eh_vendedor=True, ativo=True)
        Colaborador.objects.create(nome='C1', codigo='C1', eh_comprador=True, ativo=True)
        r = self.client.get('/api/colaboradores/', {'funcao': 'vendedor', 'ativo': 'true'})
        nomes = [x['nome'] for x in r.data]
        self.assertEqual(nomes, ['V1'])

    def test_filtrar_comprador(self):
        Colaborador.objects.create(nome='Comprador X', eh_comprador=True, ativo=True)
        r = self.client.get('/api/colaboradores/', {'funcao': 'comprador'})
        self.assertEqual(len(r.data), 1)

    def test_vincular_usuario_e_endpoint_vinculado(self):
        Colaborador.objects.create(
            nome='Meu Colab',
            codigo='MC',
            usuario=self.user,
            eh_vendedor=True,
            ativo=True,
        )
        r = self.client.get('/api/colaboradores/vinculado/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['codigo'], 'MC')
        self.assertTrue(r.data['eh_vendedor'])

    def test_vendedor_legado_continua_api(self):
        v = Vendedor.objects.create(nome='V Legado', codigo='VL', ativo=True)
        r = self.client.get(f'/api/vendedores/{v.pk}/')
        self.assertEqual(r.status_code, 200)

    def test_listagem_expoe_usuario_login(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.create_user('colab_user', 'colab_user@test.com', 'x')
        Colaborador.objects.create(nome='Com Login', codigo='CL', usuario=u, ativo=True)
        r = self.client.get('/api/colaboradores/')
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.data if x['codigo'] == 'CL')
        self.assertEqual(row['usuario_login'], 'colab_user')

    def test_colaborador_vendedor_sincroniza_vendedor(self):
        c = Colaborador.objects.create(nome='Sync Test', eh_vendedor=True, ativo=True)
        v = Vendedor.objects.filter(colaborador=c).first()
        self.assertIsNotNone(v)
        self.assertEqual(v.nome, 'Sync Test')
