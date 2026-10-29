"""API de anexos das notas internas do chatter (Sprint 3.15)."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chatter.models import AnexoChatter, NotaChatter

LIMITE_MB = 10 * 1024 * 1024


class AnexoChatterApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.autor = User.objects.create_user('an_autor', 'an_autor@test.local', 'secret')
        self.outro = User.objects.create_user('an_outro', 'an_outro@test.local', 'secret')
        self.nota_url = '/api/chatter/notas/'
        self.url = '/api/chatter/anexos/'

        # Arquivos vão para um MEDIA_ROOT descartável: nada de escrever no media/ do DEV.
        self.media_root = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        self.nota = NotaChatter.objects.create(entity_type='familia', entity_id=94, autor=self.autor, texto='Nota')

    def _arquivo(self, nome='laudo.pdf', conteudo=b'%PDF-1.4 teste'):
        return SimpleUploadedFile(nome, conteudo, content_type='application/pdf')

    def _upload(self, usuario, arquivo, nota_id=None):
        self.client.force_authenticate(user=usuario)
        return self.client.post(
            self.url,
            {'nota': nota_id if nota_id is not None else self.nota.pk, 'arquivo': arquivo},
            format='multipart',
        )

    def test_upload_valido_grava_nome_e_tamanho_do_arquivo(self):
        r = self._upload(self.autor, self._arquivo('laudo.pdf', b'%PDF-1.4 1234'))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        anexo = AnexoChatter.objects.get(pk=r.data['id'])
        self.assertEqual(anexo.nome_original, 'laudo.pdf')
        self.assertEqual(anexo.tamanho_bytes, 13)
        self.assertEqual(anexo.nota_id, self.nota.pk)

    def test_payload_nao_forja_nome_nem_tamanho(self):
        self.client.force_authenticate(user=self.autor)
        r = self.client.post(
            self.url,
            {
                'nota': self.nota.pk,
                'arquivo': self._arquivo('real.pdf', b'%PDF-1.4 1234'),
                'nome_original': 'disfarcado.xlsx',
                'tamanho_bytes': 1,
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['nome_original'], 'real.pdf')
        self.assertEqual(r.data['tamanho_bytes'], 13)

    def test_url_do_anexo_e_raiz_relativa_fora_do_prefixo_api(self):
        r = self._upload(self.autor, self._arquivo())
        self.assertTrue(r.data['arquivo_url'].startswith('/media/chatter/anexos/'), r.data['arquivo_url'])
        self.assertNotIn('/api/', r.data['arquivo_url'])

    def test_acima_de_10mb_rejeitado_com_mensagem_clara(self):
        r = self._upload(self.autor, self._arquivo('grande.pdf', b'%PDF-1.4' + b'x' * (LIMITE_MB + 1)))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('arquivo', r.data)
        self.assertIn('10 MB', str(r.data['arquivo'][0]))
        self.assertEqual(AnexoChatter.objects.count(), 0)

    def test_extensao_fora_da_whitelist_rejeitada(self):
        r = self._upload(self.autor, self._arquivo('malware.pdf.exe'))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('não permitido', str(r.data['arquivo'][0]))
        self.assertEqual(AnexoChatter.objects.count(), 0)

    def test_extensoes_da_whitelist_sao_aceitas_sem_distinguir_caixa(self):
        for nome in ('a.PDF', 'b.png', 'c.jpeg', 'd.xml', 'e.csv', 'f.docx', 'g.xlsx'):
            r = self._upload(self.autor, self._arquivo(nome, b'x'))
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, nome)

    def test_lista_filtra_por_nota(self):
        outra = NotaChatter.objects.create(entity_type='familia', entity_id=94, autor=self.autor, texto='Outra')
        self._upload(self.autor, self._arquivo('um.pdf'))
        self._upload(self.autor, self._arquivo('dois.pdf', b'%PDF'), outra.pk)

        self.client.force_authenticate(user=self.outro)
        r = self.client.get(self.url, {'nota': outra.pk})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['nome_original'], 'dois.pdf')

    def test_nota_expoe_anexos_aninhados(self):
        self._upload(self.autor, self._arquivo('anexo-unico.pdf'))

        self.client.force_authenticate(user=self.outro)
        r = self.client.get(self.nota_url, {'entity_type': 'familia', 'entity_id': 94})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        anexos = r.data['results'][0]['anexos']
        self.assertEqual(len(anexos), 1)
        self.assertEqual(anexos[0]['nome_original'], 'anexo-unico.pdf')

    def test_autor_exclui_e_o_arquivo_fisico_sai_do_storage(self):
        r = self._upload(self.autor, self._arquivo('removivel.pdf'))
        anexo = AnexoChatter.objects.get(pk=r.data['id'])
        nome_no_storage = anexo.arquivo.name
        self.assertTrue(default_storage.exists(nome_no_storage))

        d = self.client.delete(f'{self.url}{anexo.pk}/')
        self.assertEqual(d.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AnexoChatter.objects.filter(pk=anexo.pk).exists())
        # Premissa da TAREFA 3: precisa de signal/override, ou o Collector do Django já apaga?
        self.assertFalse(default_storage.exists(nome_no_storage))

    def test_terceiro_nao_exclui_anexo_e_arquivo_permance(self):
        r = self._upload(self.autor, self._arquivo('protegido.pdf'))
        anexo = AnexoChatter.objects.get(pk=r.data['id'])
        nome_no_storage = anexo.arquivo.name

        self.client.force_authenticate(user=self.outro)
        d = self.client.delete(f'{self.url}{anexo.pk}/')
        self.assertEqual(d.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(AnexoChatter.objects.filter(pk=anexo.pk).exists())
        self.assertTrue(default_storage.exists(nome_no_storage))

    def test_superuser_pode_excluir_anexo_alheio(self):
        admin = get_user_model().objects.create_superuser('an_admin', 'an_admin@test.local', 'secret')
        r = self._upload(self.autor, self._arquivo('admin.pdf'))
        anexo = AnexoChatter.objects.get(pk=r.data['id'])

        self.client.force_authenticate(user=admin)
        d = self.client.delete(f'{self.url}{anexo.pk}/')
        self.assertEqual(d.status_code, status.HTTP_204_NO_CONTENT)

    def test_excluir_a_nota_em_cascade_apaga_os_anexos(self):
        r = self._upload(self.autor, self._arquivo('filho.pdf'))
        anexo = AnexoChatter.objects.get(pk=r.data['id'])
        nome_no_storage = anexo.arquivo.name

        self.client.force_authenticate(user=self.autor)
        d = self.client.delete(f'{self.nota_url}{self.nota.pk}/')
        self.assertEqual(d.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AnexoChatter.objects.count(), 0)
        self.assertFalse(default_storage.exists(nome_no_storage))

    def test_upload_sem_autenticacao_401(self):
        arquivo = self._arquivo()
        self.client.force_authenticate(user=None)
        r = self.client.post(self.url, {'nota': self.nota.pk, 'arquivo': arquivo}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
