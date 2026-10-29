"""API de notas internas do chatter."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chatter.models import NotaChatter


class NotaChatterApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.autor = User.objects.create_user('ch_autor', 'ch_autor@test.local', 'secret')
        self.outro = User.objects.create_user('ch_outro', 'ch_outro@test.local', 'secret')
        self.url = '/api/chatter/notas/'

    def _criar(self, usuario, entity_type='familia', entity_id=13, texto='Nota de teste'):
        self.client.force_authenticate(user=usuario)
        return self.client.post(
            self.url,
            {'entity_type': entity_type, 'entity_id': entity_id, 'texto': texto},
            format='json',
        )

    def test_nao_autenticado_401(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_criar_grava_autor_do_request_nao_do_payload(self):
        r = self._criar(self.autor)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['autor'], self.autor.pk)
        self.assertEqual(r.data['autor_nome'], self.autor.get_username())
        self.assertEqual(NotaChatter.objects.count(), 1)

    def test_lista_filtra_por_entidade(self):
        self._criar(self.autor, entity_type='familia', entity_id=13, texto='A')
        self._criar(self.autor, entity_type='familia', entity_id=14, texto='B')
        self._criar(self.autor, entity_type='cliente', entity_id=13, texto='C')

        self.client.force_authenticate(user=self.outro)
        r = self.client.get(self.url, {'entity_type': 'familia', 'entity_id': 13})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['texto'], 'A')

    def test_qualquer_autenticado_le_as_notas(self):
        self._criar(self.autor)
        self.client.force_authenticate(user=self.outro)
        r = self.client.get(self.url, {'entity_type': 'familia', 'entity_id': 13})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)

    def test_ordernacaoMaisRecentePrimeiro(self):
        mais_antiga = self._criar(self.autor, texto='mais antiga').data['id']
        mais_nova = self._criar(self.autor, texto='mais nova').data['id']
        self.client.force_authenticate(user=self.autor)
        r = self.client.get(self.url, {'entity_type': 'familia', 'entity_id': 13})
        self.assertEqual([n['id'] for n in r.data['results']], [mais_nova, mais_antiga])

    def test_autor_pode_editar_e_excluir_a_propria_nota(self):
        nota_id = self._criar(self.autor).data['id']

        self.client.force_authenticate(user=self.autor)
        r = self.client.patch(f'{self.url}{nota_id}/', {'texto': 'Editada pelo autor'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['texto'], 'Editada pelo autor')

        r = self.client.delete(f'{self.url}{nota_id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(NotaChatter.objects.count(), 0)

    def test_terceiro_nao_edita_nem_exclui(self):
        nota_id = self._criar(self.autor).data['id']

        self.client.force_authenticate(user=self.outro)
        r = self.client.patch(f'{self.url}{nota_id}/', {'texto': 'invasão'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(NotaChatter.objects.get(pk=nota_id).texto, 'Nota de teste')

        r = self.client.delete(f'{self.url}{nota_id}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(NotaChatter.objects.count(), 1)

    def test_entity_type_normalizado_sem_caixa_e_espacos(self):
        self._criar(self.autor, entity_type=' Familia ')
        nota = NotaChatter.objects.get()
        self.assertEqual(nota.entity_type, 'familia')

    def test_texto_vazio_rejeitado(self):
        r = self._criar(self.autor, texto='   ')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('texto', r.data)
        self.assertEqual(NotaChatter.objects.count(), 0)

    def test_entity_id_nao_numerico_rejeitado_sem_500(self):
        self.client.force_authenticate(user=self.autor)
        r = self.client.get(self.url, {'entity_type': 'familia', 'entity_id': 'abc'})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('entity_id', r.data)

    def test_superuser_pode_editar_nota_alheia(self):
        admin = get_user_model().objects.create_superuser('ch_admin', 'ch_admin@test.local', 'secret')
        nota_id = self._criar(self.autor).data['id']

        self.client.force_authenticate(user=admin)
        r = self.client.patch(f'{self.url}{nota_id}/', {'texto': 'Correção do admin'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(NotaChatter.objects.get(pk=nota_id).texto, 'Correção do admin')

    def test_nota_de_usuario_excluido_nao_e_editavel_por_terceiro(self):
        nota_id = self._criar(self.autor).data['id']
        self.autor.delete()
        nota = NotaChatter.objects.get(pk=nota_id)
        self.assertIsNone(nota.autor)

        self.client.force_authenticate(user=self.outro)
        r = self.client.delete(f'{self.url}{nota_id}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(NotaChatter.objects.filter(pk=nota_id).exists())
