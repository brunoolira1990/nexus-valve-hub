"""ERP 4.0.13.1 — Atendimentos Operacionais (listagem AlocacaoAtendimento)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.services.alocacao_atendimento_service import criar_alocacao_atendimento
from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)
from apps.fiscal.models import AlocacaoAtendimento, AtendimentoEstoque, EstoqueCorrida
from apps.produtos.models import FamiliaProduto, Produto


def _produto(suffix: str | None = None) -> Produto:
    suf = suffix or uuid.uuid4().hex[:6]
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suf}'[:16],
        descricao_base=f'Fam {suf}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suf}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suf}',
        unidade='PC',
        ncm='84818099',
    )


class AtendimentosOperacionais40131Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('op40131', 'op@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('40131')
        self.cliente = Cliente.objects.create(
            razao_social='DYNATECH INDUSTRIAS QUIMICAS LTDA',
            cnpj='11.111.111/0001-88',
        )
        self.fornecedor = Fornecedor.objects.create(
            razao_social='FORNECEDOR XYZ LTDA',
            cnpj='22.222.222/0001-88',
        )
        self.pv = PedidoVenda.objects.create(
            numero='PV-20260521-0002',
            cliente=self.cliente,
            data=date(2026, 5, 21),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('100'),
        )
        self.aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('10'),
                'quantidade_atendida': Decimal('4'),
                'quantidade_pendente': Decimal('6'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
                'origem_fisica': OrigemFisica.FORNECEDOR,
                'destino_fisico': DestinoFisico.CLIENTE,
                'fornecedor': self.fornecedor,
            },
        )

    def test_lista_atendimentos_operacionais(self):
        r = self.client.get('/api/atendimentos-operacionais/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertGreaterEqual(data['count'], 1)
        row = next(x for x in data['results'] if x['id'] == self.aloc.pk)
        self.assertEqual(row['pedido_venda']['numero'], 'PV-20260521-0002')
        self.assertEqual(row['cliente']['nome'], 'DYNATECH INDUSTRIAS QUIMICAS LTDA')
        self.assertEqual(row['produto']['codigo'], self.produto.codigo_completo)

    def test_search_pv(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'search': 'PV-20260521'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_search_cliente(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'search': 'DYNATECH'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_search_produto(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'search': self.produto.codigo_completo})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_filtro_tipo_atendimento(self):
        r = self.client.get(
            '/api/atendimentos-operacionais/',
            {'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        for row in r.json()['results']:
            self.assertEqual(row['tipo_atendimento'], TipoAtendimentoItem.RETIRADA_FORNECEDOR)

    def test_filtro_status_entrada_fiscal(self):
        r = self.client.get(
            '/api/atendimentos-operacionais/',
            {'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_somente_pendentes(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'somente_pendentes': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_somente_sem_compra(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'somente_sem_compra': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_sem_xml_no_retorno(self):
        r = self.client.get('/api/atendimentos-operacionais/')
        body = r.content.decode('utf-8')
        self.assertNotIn('<NFe', body)
        self.assertNotIn('xml_completo', body)

    def test_paginacao(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'page': 1, 'page_size': 20})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['page_size'], 20)
        self.assertIn('total_pages', data)

    def test_listagem_queries_limitadas(self):
        pv2 = PedidoVenda.objects.create(
            numero='PV-40131-B',
            cliente=self.cliente,
            data=date(2026, 5, 22),
        )
        item2 = ItemPedidoVenda.objects.create(
            pedido=pv2,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('50'),
        )
        for _ in range(3):
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': item2,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'quantidade_atendida': Decimal('0'),
                    'quantidade_pendente': Decimal('1'),
                    'tipo_atendimento': TipoAtendimentoItem.NAO_DEFINIDO,
                },
            )
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get('/api/atendimentos-operacionais/', {'page_size': 10})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertLess(len(ctx.captured_queries), 40)

    def test_editar_nao_movimenta_estoque(self):
        antes = EstoqueCorrida.objects.count()
        r = self.client.patch(
            f'/api/alocacoes-atendimento/{self.aloc.pk}/',
            {
                'quantidade_atendida': '5.000',
                'quantidade_pendente': '5.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(EstoqueCorrida.objects.count(), antes)

    def test_editar_nao_gera_financeiro(self):
        from apps.contabil.models import Lancamento

        antes = Lancamento.objects.count()
        self.client.patch(
            f'/api/alocacoes-atendimento/{self.aloc.pk}/',
            {'observacao_operacional': 'teste 40131'},
            format='json',
        )
        self.assertEqual(Lancamento.objects.count(), antes)

    def test_editar_nao_cria_expedicao(self):
        try:
            from apps.expedicao.models import Expedicao
        except ImportError:
            self.skipTest('Módulo expedição não instalado')
        antes = Expedicao.objects.count()
        self.client.patch(
            f'/api/alocacoes-atendimento/{self.aloc.pk}/',
            {'tipo_atendimento': TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE},
            format='json',
        )
        self.assertEqual(Expedicao.objects.count(), antes)

    def test_permissoes_autenticado(self):
        anon = APIClient()
        r = anon.get('/api/atendimentos-operacionais/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dados_antigos_sem_alocacao_nao_quebram(self):
        AtendimentoEstoque.objects.all().delete()
        r = self.client.get('/api/atendimentos-operacionais/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_kpis_endpoint(self):
        r = self.client.get('/api/atendimentos-operacionais/kpis/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertIn('total', data)
        self.assertGreaterEqual(data['total'], 1)

    def test_filtro_cte_vinculado_vazio(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'tem_cte_vinculado': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertNotIn(self.aloc.pk, ids)
