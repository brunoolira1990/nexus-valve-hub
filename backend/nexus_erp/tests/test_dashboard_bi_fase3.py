"""Dashboard BI — fase 3: otimizações, expedição e KPIs entrada própria / CT-e."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import PedidoCompra, PedidoVenda
from apps.corridas.models import Corrida
from apps.expedicao.models import Expedicao, StatusExpedicao, TipoOperacaoExpedicao
from apps.fiscal.models import CTeHistoricoImportado, EstoqueCorrida, NFeEntrada
from apps.produtos.models import Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class DashboardBIFase3Tests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('bi_fase3', 'admin@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.hoje = timezone.localdate()
        self.cliente = Cliente.objects.create(razao_social='Cliente F3', cnpj=_cnpj(), uf='SC')
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn F3', cnpj=_cnpj(), uf='SC')

    def test_comercial_valor_aberto_agrega_pedidos(self):
        PedidoVenda.objects.create(
            numero='PV-F3-A',
            cliente=self.cliente,
            data=self.hoje,
            status='ABERTO',
            valor_total=Decimal('150.50'),
        )
        PedidoVenda.objects.create(
            numero='PV-F3-B',
            cliente=self.cliente,
            data=self.hoje,
            status='ABERTO',
            valor_total=Decimal('49.50'),
        )
        PedidoVenda.objects.create(
            numero='PV-F3-C',
            cliente=self.cliente,
            data=self.hoje,
            status='FATURADO',
            valor_total=Decimal('999'),
        )
        data = self.client.get('/api/dashboard/comercial/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertEqual(k['valor_aberto']['valor'], '200.00')

    def test_compras_valor_aberto_agrega_pedidos(self):
        PedidoCompra.objects.create(
            numero='PC-F3-A',
            fornecedor=self.fornecedor,
            data=self.hoje,
            status='ABERTO',
            valor_total=Decimal('80'),
        )
        PedidoCompra.objects.create(
            numero='PC-F3-B',
            fornecedor=self.fornecedor,
            data=self.hoje,
            status='ABERTO',
            valor_total=Decimal('20'),
        )
        data = self.client.get('/api/dashboard/compras/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertEqual(k['valor_aberto_compras']['valor'], '100.00')

    def test_estoque_baixo_sem_limite_500(self):
        produtos = []
        for i in range(3):
            p = Produto.objects.create(
                codigo_completo=f'BI-F3-{i}',
                descricao=f'Produto F3 {i}',
                material='Aço',
                estoque_minimo=Decimal('10'),
            )
            produtos.append(p)
            corrida = Corrida.objects.create(
                numero=f'CORR-F3-{i}',
                produto=p,
                fornecedor=self.fornecedor,
                data_recebimento=self.hoje,
            )
            EstoqueCorrida.objects.create(
                produto=p,
                corrida=corrida,
                saldo=Decimal('5') if i == 0 else Decimal('50'),
            )
        data = self.client.get('/api/dashboard/estoque/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertEqual(k['estoque_baixo']['valor'], 1)
        self.assertEqual(k['saldo_negativo']['valor'], 0)

    def test_fiscal_kpis_entrada_propria_e_cte(self):
        NFeEntrada.objects.create(
            numero='600',
            serie='1',
            chave_acesso='6' * 44,
            fornecedor=self.fornecedor,
            data=self.hoje,
            valor_total=Decimal('100'),
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        )
        dh = timezone.make_aware(datetime(2026, 6, 1, 10, 0, 0))
        CTeHistoricoImportado.objects.create(
            chave_acesso='7' * 44,
            numero='700',
            serie='1',
            dh_emissao=dh,
            valor_total_servico=Decimal('50'),
        )
        data = self.client.get('/api/dashboard/fiscal/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['nfe_entrada_propria']['valor'], 1)
        self.assertGreaterEqual(k['cte_historico_importado']['valor'], 1)

    def test_expedicao_painel_bi(self):
        Expedicao.objects.create(
            codigo='EXP-F3-01',
            tipo_operacao=TipoOperacaoExpedicao.ESTOQUE_PROPRIO,
            status=StatusExpedicao.AGUARDANDO_SEPARACAO,
            cliente=self.cliente,
        )
        Expedicao.objects.create(
            codigo='EXP-F3-02',
            tipo_operacao=TipoOperacaoExpedicao.RETIRADA_FORNECEDOR,
            status=StatusExpedicao.OCORRENCIA,
            fornecedor=self.fornecedor,
        )
        data = self.client.get('/api/dashboard/expedicao/').json()
        self.assertEqual(data['modulo'], 'expedicao')
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['exp_total']['valor'], 2)
        self.assertGreaterEqual(k['exp_ocorrencia']['valor'], 1)
        self.assertEqual(data['hero_kpi_id'], 'exp_ocorrencia')
        alertas = [a['titulo'] for a in data.get('alertas', [])]
        self.assertIn('Ocorrências em expedição', alertas)

    def test_home_inclui_expedicao(self):
        Expedicao.objects.create(
            codigo='EXP-F3-HOME',
            tipo_operacao=TipoOperacaoExpedicao.ESTOQUE_PROPRIO,
            status=StatusExpedicao.EM_TRANSITO,
            cliente=self.cliente,
        )
        data = self.client.get('/api/dashboard/home/').json()
        modulos = {m['modulo'] for m in data['modulos']}
        self.assertIn('expedicao', modulos)
        self.assertTrue(data['permissoes']['pode_ver_expedicao'])

    def test_permissoes_expedicao_endpoint(self):
        data = self.client.get('/api/dashboard/permissoes/').json()
        self.assertIn('pode_ver_expedicao', data)
        self.assertTrue(data['pode_ver_expedicao'])
