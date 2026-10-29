"""Histórico de auditoria da Família/Figura (Sprint 3.14 — aba Histórico do chatter)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auditoria.models import RegistroAuditoria
from apps.produtos.models import FamiliaProduto
from apps.produtos.serializers import FamiliaProdutoSerializer


class FamiliaHistoricoTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('fam_hist', 'fam_hist@test.local', 'secret')
        ct = ContentType.objects.get_for_model(RegistroAuditoria)
        self.user.user_permissions.add(Permission.objects.get(content_type=ct, codename='view_registroauditoria'))

    def _familia(self) -> FamiliaProduto:
        return FamiliaProduto.objects.create(
            codigo_figura='0013',
            descricao_base='FLANGE CEGO INOX 316L 4 POL',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.FLANGE,
        )

    def test_create_registra_auditoria_como_familiaproduto(self):
        serializer = FamiliaProdutoSerializer(
            data={
                'codigo_figura': '0099',
                'descricao_base': 'VALVULA GUILHOTINA TESTE',
                'tipo_regra_codigo': FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
                'modo_codigo': 'MANUAL',
            },
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        familia = serializer.save()

        registro = RegistroAuditoria.objects.get(app_label='produtos', model_name='familiaproduto')
        self.assertEqual(registro.object_id, familia.pk)
        self.assertEqual(registro.operacao, 'CREATE')
        self.assertEqual(registro.alteracoes['descricao_base']['depois'], 'VALVULA GUILHOTINA TESTE')

    def test_update_registra_apenas_o_campo_alterado(self):
        familia = self._familia()
        serializer = FamiliaProdutoSerializer(
            instance=familia,
            data={'descricao_base': 'FLANGE CEGO INOX 304 4 POL'},
            partial=True,
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        registro = RegistroAuditoria.objects.get(model_name='familiaproduto', operacao='UPDATE')
        self.assertEqual(
            registro.alteracoes['descricao_base'],
            {'antes': 'FLANGE CEGO INOX 316L 4 POL', 'depois': 'FLANGE CEGO INOX 304 4 POL'},
        )
        self.assertNotIn('codigo_figura', registro.alteracoes)

    def test_flags_derivadas_nao_entram_no_diff(self):
        """usa_* são função de tipo_regra_codigo no save(); auditá-las seria diff duplicado."""
        familia = self._familia()
        serializer = FamiliaProdutoSerializer(
            instance=familia,
            data={'tipo_regra_codigo': FamiliaProduto.TipoRegraCodigo.BASE_SCHEDULE_POLEGADA},
            partial=True,
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        registro = RegistroAuditoria.objects.get(model_name='familiaproduto', operacao='UPDATE')
        self.assertIn('tipo_regra_codigo', registro.alteracoes)
        for campo in ('usa_schedule', 'usa_rosca_conexao', 'usa_polegada_principal'):
            self.assertNotIn(campo, registro.alteracoes)

    def test_api_de_historico_devolve_200_para_familia(self):
        """A chave ('produtos','familiaproduto') precisa estar na allowlist — senão a aba pega 404."""
        familia = self._familia()
        RegistroAuditoria.objects.create(
            app_label='produtos',
            model_name='familiaproduto',
            object_id=familia.pk,
            operacao='UPDATE',
            alteracoes={'norma_base': {'antes': None, 'depois': 'ANSI B16.5'}},
            ator=self.user,
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(f'/api/auditoria/objetos/produtos/familiaproduto/{familia.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['alteracoes']['norma_base']['depois'], 'ANSI B16.5')

    def test_model_name_familia_continua_fora_de_escopo(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/auditoria/objetos/produtos/familia/13/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
