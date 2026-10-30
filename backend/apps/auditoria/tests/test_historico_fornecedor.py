"""Histórico de auditoria de Fornecedor e Transportadora (Sprint 3.16 — rail do chatter).

Espelha test_historico_familia.py: o que se prova aqui é que a escrita pelos
serializers gera o registro com a MESMA chave que a consulta de histórico aceita.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auditoria.models import RegistroAuditoria
from apps.cadastros.models import Fornecedor, Transportadora
from apps.cadastros.serializers import FornecedorSerializer, TransportadoraSerializer

# Mesmo CNPJ dos testes existentes de cadastros, já na forma normalizada que o
# serializer grava: assim o snapshot "antes" do model bate com o "depois" do payload
# e um cnpj inalterado não gera diff mascarado falso.
CNPJ_VALIDO = '11222333000181'


class FornecedorHistoricoTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('for_hist', 'for_hist@test.local', 'secret')
        ct = ContentType.objects.get_for_model(RegistroAuditoria)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='view_registroauditoria')
        )

    def _fornecedor(self, **kwargs) -> Fornecedor:
        dados = {
            'razao_social': 'SUPRIMENTOS INDUSTRIAIS LTDA',
            'cnpj': CNPJ_VALIDO,
            'prazo_entrega': 10,
            'ativo': True,
        }
        dados.update(kwargs)
        return Fornecedor.objects.create(**dados)

    def test_create_registra_auditoria_como_fornecedor(self):
        serializer = FornecedorSerializer(
            data={'razao_social': 'COMERCIAL VALES LTDA', 'cnpj': CNPJ_VALIDO},
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        fornecedor = serializer.save()

        registro = RegistroAuditoria.objects.get(app_label='cadastros', model_name='fornecedor')
        self.assertEqual(registro.object_id, fornecedor.pk)
        self.assertEqual(registro.operacao, 'CREATE')
        self.assertEqual(registro.alteracoes['razao_social']['depois'], 'COMERCIAL VALES LTDA')

    def test_update_registra_apenas_o_campo_alterado(self):
        fornecedor = self._fornecedor()
        serializer = FornecedorSerializer(
            instance=fornecedor,
            data={'razao_social': 'SUPRIMENTOS INDUSTRIAIS EIRELI'},
            partial=True,
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        registro = RegistroAuditoria.objects.get(model_name='fornecedor', operacao='UPDATE')
        self.assertEqual(
            registro.alteracoes['razao_social'],
            {'antes': 'SUPRIMENTOS INDUSTRIAIS LTDA', 'depois': 'SUPRIMENTOS INDUSTRIAIS EIRELI'},
        )
        self.assertNotIn('prazo_entrega', registro.alteracoes)
        self.assertNotIn('ativo', registro.alteracoes)

    def test_campo_mascarado_nao_grava_valor(self):
        """CNPJ está na allowlist mas mascarada: o histórico sabe que mudou, nunca o valor."""
        fornecedor = self._fornecedor()
        serializer = FornecedorSerializer(
            instance=fornecedor,
            data={'cnpj': '11.222.333/0001-81', 'email': 'novo@fornecedor.test'},
            partial=True,
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        registro = RegistroAuditoria.objects.get(model_name='fornecedor', operacao='UPDATE')
        self.assertNotIn('cnpj', registro.alteracoes)  # mesmo valor → sem diff
        self.assertEqual(
            registro.alteracoes['email'],
            {'sensivel': True, 'alterado': True},
        )

    def test_update_sem_diff_nao_grava_registro(self):
        fornecedor = self._fornecedor()
        serializer = FornecedorSerializer(
            instance=fornecedor,
            data={'razao_social': fornecedor.razao_social},
            partial=True,
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertFalse(
            RegistroAuditoria.objects.filter(model_name='fornecedor').exists(),
            'diff vazio não pode produzir registro de auditoria',
        )

    def test_api_de_historico_devolve_200_para_fornecedor(self):
        fornecedor = self._fornecedor()
        RegistroAuditoria.objects.create(
            app_label='cadastros',
            model_name='fornecedor',
            object_id=fornecedor.pk,
            operacao='UPDATE',
            alteracoes={'prazo_entrega': {'antes': 10, 'depois': 15}},
            ator=self.user,
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(f'/api/auditoria/objetos/cadastros/fornecedor/{fornecedor.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['alteracoes']['prazo_entrega']['depois'], 15)


class TransportadoraHistoricoTests(APITestCase):
    def _transportadora(self, **kwargs) -> Transportadora:
        dados = {
            'razao_social': 'TRANSPORTADORA RAPIDA LTDA',
            'cnpj': CNPJ_VALIDO,
            'placa_padrao': 'ABC1D23',
            'uf_placa': 'SP',
            'ativo': True,
        }
        dados.update(kwargs)
        return Transportadora.objects.create(**dados)

    def test_update_registra_auditoria_como_transportadora(self):
        transportadora = self._transportadora()
        serializer = TransportadoraSerializer(
            instance=transportadora,
            data={'placa_padrao': 'XYZ9A88', 'uf_placa': 'RJ'},
            partial=True,
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        registro = RegistroAuditoria.objects.get(app_label='cadastros', model_name='transportadora')
        self.assertEqual(registro.object_id, transportadora.pk)
        self.assertEqual(registro.operacao, 'UPDATE')
        self.assertEqual(registro.alteracoes['placa_padrao']['depois'], 'XYZ9A88')
        self.assertEqual(registro.alteracoes['uf_placa']['depois'], 'RJ')

    def test_create_registra_auditoria_de_transportadora(self):
        serializer = TransportadoraSerializer(
            data={'razao_social': 'LOG CENTRAL LTDA', 'cnpj': CNPJ_VALIDO},
            context={'request': None},
        )
        serializer.is_valid(raise_exception=True)
        transportadora = serializer.save()

        registro = RegistroAuditoria.objects.get(model_name='transportadora', operacao='CREATE')
        self.assertEqual(registro.object_id, transportadora.pk)
        self.assertEqual(registro.alteracoes['razao_social']['depois'], 'LOG CENTRAL LTDA')

    def test_api_de_historico_devolve_200_para_transportadora(self):
        transportadora = self._transportadora()
        RegistroAuditoria.objects.create(
            app_label='cadastros',
            model_name='transportadora',
            object_id=transportadora.pk,
            operacao='UPDATE',
            alteracoes={'valor_km': {'sensivel': False, 'antes': '2.50', 'depois': '3.10'}},
        )
        user = get_user_model().objects.create_superuser(
            'tra_hist', 'tra_hist@test.local', 'secret'
        )
        self.client.force_authenticate(user=user)
        r = self.client.get(
            f'/api/auditoria/objetos/cadastros/transportadora/{transportadora.pk}/'
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
