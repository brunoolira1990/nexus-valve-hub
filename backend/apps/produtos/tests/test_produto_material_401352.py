"""ERP 4.0.13.5.2 — Material de produto na API e preservação em update."""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.produtos.material import material_canonico_de_entrada, material_label_de_valor
from apps.produtos.models import FamiliaProduto, Produto


class ProdutoMaterialHelperTests(TestCase):
    def test_label_de_valor_canonico(self):
        self.assertEqual(material_label_de_valor('ACO CARBONO'), 'Aço Carbono')
        self.assertEqual(material_label_de_valor(''), '')

    def test_canonico_de_entrada_form(self):
        self.assertEqual(material_canonico_de_entrada('Aço Carbono'), 'ACO CARBONO')


class ProdutoMaterialApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='mat401352', password='x')
        self.client.force_authenticate(self.user)
        self.familia = FamiliaProduto.objects.create(
            codigo_figura='90EL',
            descricao_base='CURVA 90',
            material_base='ACO CARBONO',
            ativo=True,
        )
        self.produto = Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            descricao='CURVA 90 RL ACO CARBONO SCH 40 1"',
            material='ACO CARBONO',
            codigo_completo='018840.06',
            ncm='73079300',
            preco_venda=Decimal('10'),
        )

    def test_get_retorna_material_e_label(self):
        res = self.client.get(f'/api/produtos/{self.produto.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['material'], 'ACO CARBONO')
        self.assertEqual(res.data['material_label'], 'Aço Carbono')

    def test_produto_sem_material_retorna_null_label(self):
        self.produto.material = ''
        self.produto.save(update_fields=['material'])
        res = self.client.get(f'/api/produtos/{self.produto.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(res.data['material'], (None, ''))
        self.assertIsNone(res.data['material_label'])

    def test_patch_sem_material_preserva_existente(self):
        res = self.client.patch(
            f'/api/produtos/{self.produto.pk}/',
            {'descricao': 'CURVA 90 ATUALIZADA'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.material, 'ACO CARBONO')
        self.assertEqual(self.produto.descricao, 'CURVA 90 ATUALIZADA')

    def test_patch_material_vazio_nao_limpa(self):
        res = self.client.patch(
            f'/api/produtos/{self.produto.pk}/',
            {'material': ''},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.material, 'ACO CARBONO')

    def test_fake_produto_sem_material_nao_recebe_inventado(self):
        fake = Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            descricao='PROD NF',
            material='',
            codigo_completo='NF-TEST-1',
            preco_venda=Decimal('1'),
        )
        res = self.client.get(f'/api/produtos/{fake.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(res.data['material'], (None, ''))
        self.assertIsNone(res.data['material_label'])


class ProdutoDeleteProtecaoTests(TestCase):
    def setUp(self):
        from datetime import date

        from apps.cadastros.models import Cliente
        from apps.comercial.models import ItemPedidoVenda, PedidoVenda

        self.client = APIClient()
        user_model = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()
        self.user = user_model.objects.create_user(username='del401352', password='x')
        self.client.force_authenticate(self.user)
        self.produto = Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            descricao='ITEM VINCULADO',
            codigo_completo='VINC-1',
            preco_venda=Decimal('1'),
        )
        cli = Cliente.objects.create(
            razao_social='C',
            cnpj='99888777000166',
            uf='SP',
            cidade='SP',
            logradouro='R',
            numero='1',
            bairro='B',
            cep='01001000',
        )
        pv = PedidoVenda.objects.create(numero='PV-DEL-1', cliente=cli, data=date.today(), valor_total=Decimal('1'))
        ItemPedidoVenda.objects.create(
            pedido=pv,
            produto=self.produto,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('1'),
        )

    def test_delete_com_vinculo_retorna_mensagem_amigavel(self):
        res = self.client.delete(f'/api/produtos/{self.produto.pk}/')
        self.assertEqual(res.status_code, 409)
        self.assertIn('pedido', res.data['detail'].lower())
        self.assertIn('não pode ser excluído', res.data['detail'].lower())
