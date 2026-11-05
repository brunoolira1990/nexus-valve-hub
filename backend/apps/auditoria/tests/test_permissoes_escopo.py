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
    def test_escopo_cadastros_produtos_e_documentos(self):
        self.assertEqual(
            MODELOS_AUDITADOS,
            {
                ('cadastros', 'cliente'),
                ('cadastros', 'fornecedor'),
                ('cadastros', 'transportadora'),
                ('produtos', 'produto'),
                ('produtos', 'familiaproduto'),
                # Sprint 3.18: documentos com caminho de escrita pelo serializer/view.
                ('comercial', 'cotacaofornecedor'),
                ('comercial', 'proposta'),
                ('comercial', 'pedidovenda'),
                ('comercial', 'pedidocompra'),
                ('fiscal', 'nfesaida'),
                ('fiscal', 'nfeentrada'),
                # Fase 1 da entrada de terceiros: NF-e importada, conferência e CT-e.
                ('fiscal', 'nfeentradahistoricaimportada'),
                ('fiscal', 'nfeentradaconferencia'),
                ('fiscal', 'ctehistoricoimportado'),
            },
        )
        self.assertEqual(entidade_auditada_permitida('Cadastros', 'Cliente'), ('cadastros', 'cliente'))
        self.assertEqual(
            entidade_auditada_permitida('Cadastros', 'Fornecedor'),
            ('cadastros', 'fornecedor'),
        )
        self.assertEqual(
            entidade_auditada_permitida('cadastros', 'Transportadora'),
            ('cadastros', 'transportadora'),
        )
        self.assertEqual(
            entidade_auditada_permitida('Fiscal', 'NFeSaida'),
            ('fiscal', 'nfesaida'),
        )
        self.assertIsNone(entidade_auditada_permitida('cadastros', 'colaborador'))
        self.assertEqual(
            entidade_auditada_permitida('Produtos', 'FamiliaProduto'),
            ('produtos', 'familiaproduto'),
        )
        # 'familia' continua inválido: o model_name gravado é o nome lowercase da classe.
        self.assertIsNone(entidade_auditada_permitida('produtos', 'familia'))
        # idem para os documentos: 'nfe_saida' e 'cotacao' não são nomes de classe.
        self.assertIsNone(entidade_auditada_permitida('fiscal', 'nfe_saida'))
        self.assertIsNone(entidade_auditada_permitida('comercial', 'cotacao'))
        # CTeEntrada existe como model mas não tem escrita (ReadOnlyModelViewSet), e a
        # tela CT-e lista CTeHistoricoImportado: nenhum dos dois está no escopo ainda.
        self.assertIsNone(entidade_auditada_permitida('fiscal', 'cteentrada'))


class AuditoriaRotaEscopoApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('aud_esc', 'aud_esc@test.local', 'secret')
        self.client.force_authenticate(user=user)

    def test_fornecedor_agora_dentro_de_escopo(self):
        """Sprint 3.16: ('cadastros','fornecedor') entrou na allowlist — antes era 404."""
        RegistroAuditoria.objects.create(
            app_label='cadastros',
            model_name='fornecedor',
            object_id=7,
            operacao='CREATE',
            alteracoes={'razao_social': {'antes': None, 'depois': 'SUPRIMENTOS LTDA'}},
        )
        r = self.client.get('/api/auditoria/objetos/cadastros/fornecedor/7/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)

    def test_transportadora_agora_dentro_de_escopo(self):
        r = self.client.get('/api/auditoria/objetos/cadastros/transportadora/3/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 0)

    def test_model_fora_de_escopo_continua_404(self):
        r = self.client.get('/api/auditoria/objetos/cadastros/colaborador/1/')
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
