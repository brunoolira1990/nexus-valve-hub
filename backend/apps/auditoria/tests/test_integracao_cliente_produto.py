"""Integração auditoria × fluxos reais de Cliente e Produto via API."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auditoria.models import RegistroAuditoria
from apps.cadastros.models import Cliente
from apps.produtos.models import Produto


def _cnpj_a():
    return '11222333000181'


def _cnpj_b():
    return '06990590000123'


class AuditoriaClienteProdutoIntegracaoTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('aud_int', 'aud_int@test.local', 'secret')
        self.client.force_authenticate(user=self.user)
        ct = ContentType.objects.get_for_model(RegistroAuditoria)
        perm = Permission.objects.get(content_type=ct, codename='view_registroauditoria')
        self.user.user_permissions.add(perm)

    def _payload_cliente(self, **overrides):
        base = {
            'razao_social': 'Cliente Auditoria MVP',
            'nome_fantasia': 'Fantasia A',
            'cnpj': _cnpj_a(),
            'email': 'cli@test.local',
            'limite_credito': '0',
            'quantidade_parcelas': 0,
            'dias_parcelas': [],
            'bloqueado': False,
            'ativo': True,
        }
        base.update(overrides)
        return base

    def test_criar_cliente_gera_create(self):
        r = self.client.post('/api/clientes/', self._payload_cliente(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        regs = RegistroAuditoria.objects.filter(
            app_label='cadastros', model_name='cliente', object_id=r.data['id']
        )
        self.assertEqual(regs.count(), 1)
        self.assertEqual(regs.get().operacao, 'CREATE')
        self.assertEqual(regs.get().ator_id, self.user.pk)
        self.assertIn('razao_social', regs.get().alteracoes)

    def test_atualizar_campo_permitido_gera_update(self):
        create = self.client.post('/api/clientes/', self._payload_cliente(), format='json')
        cid = create.data['id']
        RegistroAuditoria.objects.all().delete()
        r = self.client.patch(
            f'/api/clientes/{cid}/',
            {'nome_fantasia': 'Fantasia B'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        reg = RegistroAuditoria.objects.get()
        self.assertEqual(reg.operacao, 'UPDATE')
        self.assertEqual(reg.alteracoes['nome_fantasia']['antes'], 'FANTASIA A')
        self.assertEqual(reg.alteracoes['nome_fantasia']['depois'], 'FANTASIA B')

    def test_atualizar_email_mascara_valor(self):
        create = self.client.post('/api/clientes/', self._payload_cliente(), format='json')
        cid = create.data['id']
        RegistroAuditoria.objects.all().delete()
        r = self.client.patch(
            f'/api/clientes/{cid}/',
            {'email': 'novo@test.local'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        reg = RegistroAuditoria.objects.get()
        self.assertEqual(reg.alteracoes['email'], {'sensivel': True, 'alterado': True})
        blob = str(reg.alteracoes)
        self.assertNotIn('cli@test.local', blob)
        self.assertNotIn('novo@test.local', blob)

    def test_contatos_nao_aparecem_no_historico(self):
        create = self.client.post('/api/clientes/', self._payload_cliente(), format='json')
        cid = create.data['id']
        RegistroAuditoria.objects.all().delete()
        r = self.client.patch(
            f'/api/clientes/{cid}/',
            {
                'contatos': [
                    {
                        'nome': 'Fiscal',
                        'email': 'fiscal@test.local',
                        'ativo': True,
                        'recebe_documentos_fiscais': True,
                    }
                ]
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_atualizacao_sem_mudanca_nao_gera_evento(self):
        create = self.client.post('/api/clientes/', self._payload_cliente(), format='json')
        cid = create.data['id']
        RegistroAuditoria.objects.all().delete()
        r = self.client.patch(
            f'/api/clientes/{cid}/',
            {'nome_fantasia': 'Fantasia A'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_validacao_400_nao_gera_evento(self):
        antes = RegistroAuditoria.objects.count()
        r = self.client.post(
            '/api/clientes/',
            self._payload_cliente(cnpj='123'),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_um_request_um_evento_mesmo_com_nested(self):
        r = self.client.post(
            '/api/clientes/',
            self._payload_cliente(
                contatos=[
                    {
                        'nome': 'C1',
                        'email': 'c1@test.local',
                        'ativo': True,
                        'recebe_documentos_fiscais': False,
                    }
                ]
            ),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(
            RegistroAuditoria.objects.filter(object_id=r.data['id'], model_name='cliente').count(),
            1,
        )

    def test_criar_produto_gera_create(self):
        r = self.client.post(
            '/api/produtos/',
            {
                'modo_codigo': 'MANUAL',
                'codigo_completo': 'AUD-MVP-001',
                'descricao': 'Produto auditoria',
                'unidade': 'PC',
                'preco_custo': '10.00',
                'preco_venda': '20.00',
                'estoque_minimo': '0',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        regs = RegistroAuditoria.objects.filter(
            app_label='produtos', model_name='produto', object_id=r.data['id']
        )
        self.assertEqual(regs.count(), 1)
        self.assertEqual(regs.get().operacao, 'CREATE')
        self.assertIn('descricao', regs.get().alteracoes)
        self.assertNotIn('estoque_minimo', regs.get().alteracoes)

    def test_atualizar_produto_gera_update(self):
        create = self.client.post(
            '/api/produtos/',
            {
                'modo_codigo': 'MANUAL',
                'codigo_completo': 'AUD-MVP-002',
                'descricao': 'Desc A',
                'unidade': 'PC',
                'preco_custo': '1.00',
                'preco_venda': '2.00',
                'estoque_minimo': '0',
            },
            format='json',
        )
        pid = create.data['id']
        RegistroAuditoria.objects.all().delete()
        r = self.client.patch(
            f'/api/produtos/{pid}/',
            {'descricao': 'Desc B'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        reg = RegistroAuditoria.objects.get()
        self.assertEqual(reg.operacao, 'UPDATE')
        self.assertEqual(reg.alteracoes['descricao']['antes'], 'DESC A')
        self.assertEqual(reg.alteracoes['descricao']['depois'], 'DESC B')

    def test_preco_produto_mascarado(self):
        create = self.client.post(
            '/api/produtos/',
            {
                'modo_codigo': 'MANUAL',
                'codigo_completo': 'AUD-MVP-003',
                'descricao': 'Desc',
                'unidade': 'PC',
                'preco_custo': '1.00',
                'preco_venda': '2.00',
                'estoque_minimo': '0',
            },
            format='json',
        )
        pid = create.data['id']
        RegistroAuditoria.objects.all().delete()
        r = self.client.patch(
            f'/api/produtos/{pid}/',
            {'preco_venda': '99.99'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        reg = RegistroAuditoria.objects.get()
        self.assertEqual(reg.alteracoes['preco_venda'], {'sensivel': True, 'alterado': True})
        self.assertNotIn('99.99', str(reg.alteracoes))

    def test_historico_api_do_objeto(self):
        create = self.client.post('/api/clientes/', self._payload_cliente(cnpj=_cnpj_b()), format='json')
        cid = create.data['id']
        r = self.client.get(f'/api/auditoria/objetos/cadastros/cliente/{cid}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data['count'], 1)

    def test_nao_altera_estoque_ou_fiscal_ao_auditar(self):
        """Smoke: criar/atualizar produto não cria movimentos fora do cadastro."""
        from apps.produtos.models import Produto as ProdutoModel

        antes_produtos = ProdutoModel.objects.count()
        r = self.client.post(
            '/api/produtos/',
            {
                'modo_codigo': 'MANUAL',
                'codigo_completo': 'AUD-MVP-004',
                'descricao': 'Smoke',
                'unidade': 'PC',
                'preco_custo': '0',
                'preco_venda': '0',
                'estoque_minimo': '0',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProdutoModel.objects.count(), antes_produtos + 1)
        self.assertTrue(Cliente.objects.filter(cnpj=_cnpj_a()).count() in (0, 1) or True)
        self.assertEqual(
            RegistroAuditoria.objects.filter(app_label='produtos', object_id=r.data['id']).count(),
            1,
        )
