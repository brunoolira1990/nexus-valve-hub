"""Comercial 2.3.2 — cadastro de vendedor, FK em proposta/pedido e busca."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.converter_proposta_pedido import converter_proposta_em_pedido_venda
from apps.comercial.models import ItemProposta, PedidoVenda, Proposta, Vendedor
from apps.comercial.tests.test_converter_proposta_pedido import _item, _produto, _proposta_aprovada
from apps.produtos.models import Produto

User = get_user_model()


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class VendedorComercial232Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('vend232', 'v232@test.com', 'x')
        self.outro = User.objects.create_user('outro232', 'outro@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
        self.cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')

    def test_criar_e_buscar_vendedor(self):
        r = self.client.post(
            '/api/vendedores/',
            {'nome': 'João Silva', 'codigo': 'JS', 'email': 'joao@ex.com', 'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        vid = r.data['id']
        r2 = self.client.get('/api/vendedores/', {'search': 'joao'})
        self.assertEqual(r2.status_code, 200)
        ids = [x['id'] for x in (r2.data if isinstance(r2.data, list) else r2.data.get('results', []))]
        self.assertIn(vid, ids)

    def test_vincular_vendedor_usuario_e_default_proposta(self):
        v = Vendedor.objects.create(nome='Meu Vendedor', codigo='MV', usuario=self.user, ativo=True)
        hoje = date.today().isoformat()
        payload = {
            'data': hoje,
            'validade': (date.today() + timedelta(days=15)).isoformat(),
            'cliente_id': self.cli.pk,
            'empresa_emitente_id': self.emp.pk,
            'status': 'PENDENTE',
            'condicao_pagamento_texto': '30',
            'itens': [],
        }
        r = self.client.post('/api/propostas/', payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['vendedor_id'], v.pk)
        self.assertEqual(r.data['vendedor_nome'], v.nome)
        self.assertEqual(r.data['vendedor'], 'MEU VENDEDOR')

    def test_proposta_aceita_vendedor_id_diferente_do_usuario(self):
        v = Vendedor.objects.create(nome='Outro Rep', codigo='OR', ativo=True)
        hoje = date.today().isoformat()
        payload = {
            'data': hoje,
            'validade': (date.today() + timedelta(days=15)).isoformat(),
            'cliente_id': self.cli.pk,
            'empresa_emitente_id': self.emp.pk,
            'vendedor_id': v.pk,
            'status': 'PENDENTE',
            'condicao_pagamento_texto': '30',
            'itens': [],
        }
        r = self.client.post('/api/propostas/', payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['vendedor_id'], v.pk)

    def test_proposta_legado_texto_continua_serializando(self):
        p = Proposta.objects.create(
            numero=f'LEG-{uuid.uuid4().hex[:4]}',
            data=date.today(),
            validade=date.today() + timedelta(days=10),
            empresa_emitente=self.emp,
            cliente=self.cli,
            vendedor='Vendedor Antigo Texto',
            status='PENDENTE',
        )
        r = self.client.get(f'/api/propostas/{p.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['vendedor_id'])
        self.assertEqual(r.data['vendedor_nome'], p.vendedor)
        self.assertEqual(r.data['vendedor'], p.vendedor)

    def test_conversao_herda_vendedor_fk(self):
        v = Vendedor.objects.create(nome='Rep Conv', codigo='RC', ativo=True)
        p = _proposta_aprovada()
        p.vendedor_ref = v
        p.vendedor = v.nome
        p.save(update_fields=['vendedor_ref', 'vendedor'])
        prod = _produto()
        _item(p, prod)
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.vendedor_ref_id, v.pk)
        self.assertEqual(pedido.vendedor.upper(), 'REP CONV')

    def test_item_novo_com_produto_cadastrado(self):
        prod = _produto()
        hoje = date.today().isoformat()
        payload = {
            'data': hoje,
            'validade': (date.today() + timedelta(days=15)).isoformat(),
            'cliente_id': self.cli.pk,
            'empresa_emitente_id': self.emp.pk,
            'status': 'PENDENTE',
            'condicao_pagamento_texto': '30',
            'itens': [
                {
                    'produto_id': prod.pk,
                    'quantidade': 1,
                    'quantidade_negociada': 1,
                    'valor_unitario': 10,
                    'preco_por_unidade_negociada': 10,
                    'desconto': 0,
                    'modo_preco': 'sugerido',
                },
            ],
        }
        r = self.client.post('/api/propostas/', payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data['itens']), 1)
        self.assertEqual(r.data['itens'][0]['produto_id'], prod.pk)

    def test_item_avulso_com_ncm(self):
        hoje = date.today().isoformat()
        payload = {
            'data': hoje,
            'validade': (date.today() + timedelta(days=15)).isoformat(),
            'cliente_id': self.cli.pk,
            'empresa_emitente_id': self.emp.pk,
            'status': 'PENDENTE',
            'condicao_pagamento_texto': '30',
            'itens': [
                {
                    'produto_id': None,
                    'descricao_avulsa': 'Item manual',
                    'ncm_avulso': '84818099',
                    'quantidade': 1,
                    'quantidade_negociada': 1,
                    'valor_unitario': 10,
                    'preco_por_unidade_negociada': 10,
                    'desconto': 0,
                    'modo_preco': 'sugerido',
                },
            ],
        }
        r = self.client.post('/api/propostas/', payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['itens'][0]['produto_id'])
        self.assertEqual(r.data['itens'][0]['descricao_avulsa'], 'ITEM MANUAL')

    def test_endpoint_vinculado(self):
        Vendedor.objects.create(nome='Vinc', codigo='V1', usuario=self.user, ativo=True)
        r = self.client.get('/api/vendedores/vinculado/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['codigo'], 'V1')

    def test_proposta_default_via_colaborador_vinculado(self):
        from apps.cadastros.models import Cliente, Colaborador, Empresa

        Colaborador.objects.create(
            nome='Colab Default',
            codigo='CD',
            usuario=self.user,
            eh_vendedor=True,
            ativo=True,
        )
        emp = Empresa.objects.create(razao_social='Emit CD', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='Cli CD', cnpj=_cnpj())
        hoje = date.today().isoformat()
        payload = {
            'data': hoje,
            'validade': hoje,
            'cliente_id': cli.pk,
            'empresa_emitente_id': emp.pk,
            'status': 'PENDENTE',
            'condicao_pagamento_texto': '30',
            'itens': [],
        }
        r = self.client.post('/api/propostas/', payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNotNone(r.data.get('vendedor_id'))
