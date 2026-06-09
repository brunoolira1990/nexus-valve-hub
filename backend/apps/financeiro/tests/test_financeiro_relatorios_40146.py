"""ERP 4.0.14.6 — Relatórios financeiros operacionais."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.constants import FormaPagamentoCodigo
from apps.financeiro.models import ContaFinanceira, TituloFinanceiro
from apps.financeiro.relatorios import (
    relatorio_categorias,
    relatorio_clientes,
    relatorio_contas_pagar,
    relatorio_contas_receber,
    relatorio_fluxo_previsto,
    relatorio_fornecedores,
)
from apps.financeiro.services.baixa import registrar_baixa_financeira
from apps.financeiro.services.titulo import criar_titulo_financeiro


class FinanceiroRelatorios40146Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin40146', 'fin40146@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cli = Cliente.objects.create(razao_social='Cli 40146', cnpj='39053344706')
        self.forn = Fornecedor.objects.create(razao_social='Forn 40146', cnpj='59443075000121')
        self.conta = ContaFinanceira.objects.create(nome='Conta 40146', tipo='CAIXA')
        self.hoje = timezone.localdate()

    def _criar_receber(self, vencimento: date, valor: str = '100.00', **kwargs):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cli.pk,
            data_emissao=self.hoje,
            data_vencimento=vencimento,
            valor_original=Decimal(valor),
            origem_tipo=kwargs.get('origem_tipo', TituloFinanceiro.OrigemTipo.MANUAL),
            usuario=self.user,
        )

    def _criar_pagar(self, vencimento: date, valor: str = '80.00', **kwargs):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.forn.pk,
            tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR,
            data_emissao=self.hoje,
            data_vencimento=vencimento,
            valor_original=Decimal(valor),
            origem_tipo=kwargs.get('origem_tipo', TituloFinanceiro.OrigemTipo.MANUAL),
            usuario=self.user,
        )

    def test_relatorio_cr_em_aberto(self):
        self._criar_receber(self.hoje + timedelta(days=5))
        data = relatorio_contas_receber({})
        self.assertGreater(Decimal(data['cards']['total_aberto']['valor']), 0)
        self.assertGreaterEqual(len(data['linhas']), 1)

    def test_relatorio_cr_vencidos(self):
        self._criar_receber(self.hoje - timedelta(days=3))
        res = self.client.get('/api/financeiro/relatorios/contas-receber/?vencimento=vencidos')
        self.assertEqual(res.status_code, 200)
        self.assertGreater(Decimal(res.json()['cards']['total_vencido']['valor']), 0)

    def test_relatorio_cr_agrupa_cliente(self):
        self._criar_receber(self.hoje)
        data = relatorio_contas_receber({'agrupamento': 'cliente'})
        self.assertGreaterEqual(len(data['agrupamentos']), 1)

    def test_relatorio_cr_filtro_origem_nfe(self):
        self._criar_receber(self.hoje, origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA)
        res = self.client.get(
            '/api/financeiro/relatorios/contas-receber/?origem_tipo=NFE_SAIDA',
        )
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.json()['cards']['quantidade_titulos'], 1)

    def test_relatorio_cp_em_aberto(self):
        self._criar_pagar(self.hoje + timedelta(days=4))
        data = relatorio_contas_pagar({})
        self.assertGreater(Decimal(data['cards']['total_aberto']['valor']), 0)

    def test_relatorio_cp_vencidos(self):
        self._criar_pagar(self.hoje - timedelta(days=2))
        data = relatorio_contas_pagar({'vencimento': 'vencidos'})
        self.assertGreater(Decimal(data['cards']['total_vencido']['valor']), 0)

    def test_relatorio_cp_agrupa_fornecedor(self):
        self._criar_pagar(self.hoje)
        data = relatorio_contas_pagar({'agrupamento': 'fornecedor'})
        self.assertGreaterEqual(len(data['agrupamentos']), 1)

    def test_relatorio_cp_filtro_origem_nfe_entrada(self):
        self._criar_pagar(self.hoje, origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA)
        res = self.client.get(
            '/api/financeiro/relatorios/contas-pagar/?origem_tipo=NFE_ENTRADA',
        )
        self.assertGreaterEqual(res.json()['cards']['quantidade_titulos'], 1)

    def test_fluxo_previsto_entradas_saidas(self):
        self._criar_receber(self.hoje + timedelta(days=2))
        self._criar_pagar(self.hoje + timedelta(days=2))
        data = relatorio_fluxo_previsto({'periodo': 'proximos_7'})
        self.assertGreater(Decimal(data['cards']['total_receber']['valor']), 0)
        self.assertGreater(Decimal(data['cards']['total_pagar']['valor']), 0)
        self.assertTrue(any(Decimal(l['a_receber']) > 0 for l in data['linhas']))

    def test_fluxo_previsto_saldo_acumulado(self):
        self._criar_receber(self.hoje + timedelta(days=1), valor='50.00')
        data = relatorio_fluxo_previsto({'periodo': 'proximos_7'})
        linhas = data['linhas']
        self.assertTrue(linhas)
        ultimo = Decimal(linhas[-1]['saldo_acumulado'])
        self.assertGreater(ultimo, 0)

    def test_categorias_soma_receitas_despesas(self):
        self._criar_receber(self.hoje)
        self._criar_pagar(self.hoje)
        data = relatorio_categorias({'periodo': 'mes'})
        self.assertGreater(Decimal(data['cards']['total_receitas']['valor']), 0)
        self.assertGreater(Decimal(data['cards']['total_despesas']['valor']), 0)

    def test_clientes_total_aberto_vencido(self):
        self._criar_receber(self.hoje - timedelta(days=1))
        data = relatorio_clientes({})
        self.assertGreaterEqual(len(data['resumo']), 1)
        row = data['resumo'][0]
        self.assertGreater(Decimal(row['total_aberto']), 0)
        self.assertGreater(Decimal(row['total_vencido']), 0)

    def test_fornecedores_total_aberto_vencido(self):
        self._criar_pagar(self.hoje - timedelta(days=1))
        data = relatorio_fornecedores({})
        self.assertGreaterEqual(len(data['resumo']), 1)

    def test_cancelados_nao_entram_aberto(self):
        titulo = self._criar_receber(self.hoje)
        titulo.cancelado = True
        titulo.status = TituloFinanceiro.Status.CANCELADO
        titulo.valor_aberto = Decimal('0')
        titulo.save()
        data = relatorio_contas_receber({})
        ids = [l['id'] for l in data['linhas']]
        self.assertNotIn(titulo.id, ids)
        self.assertEqual(Decimal(data['cards']['total_aberto']['valor']), Decimal('0'))

    def test_baixados_entram_periodo(self):
        titulo = self._criar_receber(self.hoje)
        registrar_baixa_financeira(
            titulo=titulo,
            valor=titulo.valor_original,
            data_baixa=self.hoje,
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.DINHEIRO,
            usuario=self.user,
        )
        data = relatorio_contas_receber({'periodo': 'mes'})
        self.assertGreater(Decimal(data['cards']['recebido_periodo']['valor']), 0)

    def test_relatorio_nao_altera_saldo(self):
        titulo = self._criar_receber(self.hoje)
        saldo_antes = titulo.valor_aberto
        self.client.get('/api/financeiro/relatorios/contas-receber/')
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, saldo_antes)
