"""Permissões append-only e escopo de rotas do MVP."""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from apps.auditoria.escopo import MODELOS_AUDITADOS, entidade_auditada_permitida
from apps.auditoria.models import RegistroAuditoria


class RegistroAuditoriaPermissoesTests(TestCase):
    def test_somente_permissao_view(self):
        ct = ContentType.objects.get_for_model(RegistroAuditoria)
        codenames = set(
            Permission.objects.filter(content_type=ct).values_list('codename', flat=True)
        )
        self.assertEqual(codenames, {'view_registroauditoria'})
        self.assertEqual(RegistroAuditoria._meta.default_permissions, ('view',))


class AuditoriaEscopoTests(TestCase):
    def test_mvp_somente_cliente_e_produto(self):
        self.assertEqual(
            MODELOS_AUDITADOS,
            {('cadastros', 'cliente'), ('produtos', 'produto')},
        )
        self.assertEqual(entidade_auditada_permitida('Cadastros', 'Cliente'), ('cadastros', 'cliente'))
        self.assertIsNone(entidade_auditada_permitida('cadastros', 'fornecedor'))
        self.assertIsNone(entidade_auditada_permitida('fiscal', 'nfesaida'))
        self.assertIsNone(entidade_auditada_permitida('produtos', 'familia'))


class AuditoriaRotaEscopoApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('aud_esc', 'aud_esc@test.local', 'secret')
        self.client.force_authenticate(user=user)

    def test_fornecedor_404(self):
        r = self.client.get('/api/auditoria/objetos/cadastros/fornecedor/1/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_produto_app_errado_404(self):
        r = self.client.get('/api/auditoria/objetos/cadastros/produto/1/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_cliente_ok_mesmo_case_misto(self):
        RegistroAuditoria.objects.create(
            app_label='cadastros',
            model_name='cliente',
            object_id=1,
            operacao='CREATE',
            alteracoes={'razao_social': {'antes': None, 'depois': 'X'}},
        )
        r = self.client.get('/api/auditoria/objetos/Cadastros/Cliente/1/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
