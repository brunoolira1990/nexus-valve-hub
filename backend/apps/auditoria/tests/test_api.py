"""API somente leitura de auditoria."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auditoria.models import RegistroAuditoria


class AuditoriaApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('aud_api', 'aud_api@test.local', 'secret')
        self.other = User.objects.create_user('aud_other', 'aud_other@test.local', 'secret')
        ct = ContentType.objects.get_for_model(RegistroAuditoria)
        self.perm = Permission.objects.get(content_type=ct, codename='view_registroauditoria')
        self.user.user_permissions.add(self.perm)

        RegistroAuditoria.objects.create(
            app_label='cadastros',
            model_name='cliente',
            object_id=10,
            operacao='UPDATE',
            alteracoes={'nome_fantasia': {'antes': 'A', 'depois': 'B'}},
            ator=self.user,
        )
        RegistroAuditoria.objects.create(
            app_label='cadastros',
            model_name='cliente',
            object_id=11,
            operacao='CREATE',
            alteracoes={'razao_social': {'antes': None, 'depois': 'Outro'}},
            ator=self.user,
        )

    def test_nao_autenticado_401(self):
        r = self.client.get('/api/auditoria/objetos/cadastros/cliente/10/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sem_permissao_403(self):
        self.client.force_authenticate(user=self.other)
        r = self.client.get('/api/auditoria/objetos/cadastros/cliente/10/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_retorna_somente_objeto_solicitado(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/auditoria/objetos/cadastros/cliente/10/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['alteracoes']['nome_fantasia']['depois'], 'B')
        self.assertEqual(r.data['results'][0]['ator']['id'], self.user.pk)
        self.assertNotIn('email', r.data['results'][0]['ator'])

    def test_capacidade(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/auditoria/capacidade/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['pode_visualizar'])
        self.client.force_authenticate(user=self.other)
        r2 = self.client.get('/api/auditoria/capacidade/')
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertFalse(r2.data['pode_visualizar'])

    def test_metodos_escrita_nao_permitidos(self):
        self.client.force_authenticate(user=self.user)
        url = '/api/auditoria/objetos/cadastros/cliente/10/'
        self.assertEqual(self.client.post(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.put(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.patch(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_entidade_nao_suportada_404(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/auditoria/objetos/fiscal/nfesaida/1/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
