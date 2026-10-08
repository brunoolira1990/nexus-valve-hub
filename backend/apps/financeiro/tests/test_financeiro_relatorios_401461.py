"""ERP 4.0.14.6.1 — Consistência dos relatórios financeiros."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

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


class FinanceiroRelatorios401461Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin401461', 'fin401461@test.com', 'x')
        self.cli = Cliente.objects.create(razao_social='Cli 401461', cnpj='39053344707')
        self.forn = Fornecedor.objects.create(razao_social='Forn 401461', cnpj='59443075000122')
        self.conta = ContaFinanceira.objects.create(nome='Conta 401461', tipo='CAIXA')
        self.hoje = timezone.localdate()

    def _criar_receber(self, vencimento=None, valor: str = '100.00'):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cli.pk,
            data_emissao=self.hoje,
            data_vencimento=vencimento or self.hoje,
            valor_original=Decimal(valor),
            origem_tipo=TituloFinanceiro.OrigemTipo.MANUAL,
            usuario=self.user,
        )

    def _criar_pagar(self, vencimento=None, valor: str = '80.00'):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.forn.pk,
            tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR,
            data_emissao=self.hoje,
            data_vencimento=vencimento or self.hoje,
            valor_original=Decimal(valor),
            origem_tipo=TituloFinanceiro.OrigemTipo.MANUAL,
            usuario=self.user,
        )

    def _pagar_receber(self, titulo):
        registrar_baixa_financeira(
            titulo=titulo,
            valor=titulo.valor_original,
            data_baixa=self.hoje,
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.DINHEIRO,
            usuario=self.user,
        )

    def test_cr_nao_inclui_cancelados_por_padrao(self):
        titulo = self._criar_receber()
        titulo.cancelado = True
        titulo.status = TituloFinanceiro.Status.CANCELADO
        titulo.valor_aberto = Decimal('0')
        titulo.save()
        data = relatorio_contas_receber({})
        self.assertNotIn(titulo.id, [l['id'] for l in data['linhas']])

    def test_cr_nao_inclui_recebidos_por_padrao(self):
        titulo = self._criar_receber()
        self._pagar_receber(titulo)
        data = relatorio_contas_receber({})
        self.assertNotIn(titulo.id, [l['id'] for l in data['linhas']])

    def test_cr_inclui_cancelados_com_flag(self):
        titulo = self._criar_receber()
        titulo.cancelado = True
        titulo.status = TituloFinanceiro.Status.CANCELADO
        titulo.valor_aberto = Decimal('0')
        titulo.save()
        data = relatorio_contas_receber({'incluir_cancelados': '1'})
        self.assertIn(titulo.id, [l['id'] for l in data['linhas']])
        self.assertIsNotNone(data.get('aviso_historico'))

    def test_cr_inclui_recebidos_com_flag(self):
        titulo = self._criar_receber()
        self._pagar_receber(titulo)
        data = relatorio_contas_receber({'incluir_quitados': '1'})
        self.assertIn(titulo.id, [l['id'] for l in data['linhas']])

    def test_cp_nao_inclui_cancelados_por_padrao(self):
        titulo = self._criar_pagar()
        titulo.cancelado = True
        titulo.status = TituloFinanceiro.Status.CANCELADO
        titulo.valor_aberto = Decimal('0')
        titulo.save()
        data = relatorio_contas_pagar({})
        self.assertNotIn(titulo.id, [l['id'] for l in data['linhas']])

    def test_cp_nao_inclui_pagos_por_padrao(self):
        titulo = self._criar_pagar()
        self._pagar_receber(titulo)
        data = relatorio_contas_pagar({})
        self.assertNotIn(titulo.id, [l['id'] for l in data['linhas']])

    def test_cp_inclui_pagos_com_flag(self):
        titulo = self._criar_pagar()
        self._pagar_receber(titulo)
        data = relatorio_contas_pagar({'incluir_quitados': '1'})
        self.assertIn(titulo.id, [l['id'] for l in data['linhas']])

    def test_cliente_zerado_oculto_por_padrao(self):
        titulo = self._criar_receber()
        self._pagar_receber(titulo)
        data = relatorio_clientes({})
        ids = [r['cliente_id'] for r in data['resumo']]
        self.assertNotIn(self.cli.pk, ids)

    def test_cliente_zerado_visivel_com_sem_saldo(self):
        titulo = self._criar_receber()
        self._pagar_receber(titulo)
        data = relatorio_clientes({'incluir_quitados': '1', 'incluir_sem_saldo': '1'})
        ids = [r['cliente_id'] for r in data['resumo']]
        self.assertIn(self.cli.pk, ids)

    def test_fornecedor_zerado_oculto_por_padrao(self):
        titulo = self._criar_pagar()
        self._pagar_receber(titulo)
        data = relatorio_fornecedores({})
        ids = [r['fornecedor_id'] for r in data['resumo']]
        self.assertNotIn(self.forn.pk, ids)

    def test_fornecedor_zerado_visivel_com_sem_saldo(self):
        titulo = self._criar_pagar()
        self._pagar_receber(titulo)
        data = relatorio_fornecedores({'incluir_quitados': '1', 'incluir_sem_saldo': '1'})
        ids = [r['fornecedor_id'] for r in data['resumo']]
        self.assertIn(self.forn.pk, ids)

    def test_categoria_separa_original_aberto_baixado(self):
        titulo = self._criar_receber(valor='288.00')
        self._pagar_receber(titulo)
        aberto = self._criar_receber(valor='50.00')
        data = relatorio_categorias({'periodo': 'mes', 'incluir_quitados': '1'})
        linhas = data['linhas']
        self.assertTrue(linhas)
        ln = linhas[0]
        self.assertIn('valor_original', ln)
        self.assertIn('em_aberto', ln)
        self.assertIn('baixado_periodo', ln)
        self.assertGreater(Decimal(ln['valor_original']), 0)
        self.assertGreater(Decimal(ln['baixado_periodo']), 0)
        aberto.refresh_from_db()
        self.assertGreater(Decimal(ln['em_aberto']), 0)

    def test_fluxo_previsto_ignora_cancelados_e_quitados(self):
        aberto = self._criar_receber(self.hoje + timedelta(days=2))
        cancelado = self._criar_receber(self.hoje + timedelta(days=2), valor='30.00')
        cancelado.cancelado = True
        cancelado.status = TituloFinanceiro.Status.CANCELADO
        cancelado.valor_aberto = Decimal('0')
        cancelado.save()
        quitado = self._criar_receber(self.hoje + timedelta(days=2), valor='20.00')
        self._pagar_receber(quitado)
        data = relatorio_fluxo_previsto({'periodo': 'proximos_7'})
        total = Decimal(data['cards']['total_receber']['valor'])
        self.assertEqual(total, aberto.valor_aberto)

    def test_cards_aberto_nao_incluem_cancelados(self):
        self._criar_receber(valor='200.00')
        cancelado = self._criar_receber(valor='500.00')
        cancelado.cancelado = True
        cancelado.status = TituloFinanceiro.Status.CANCELADO
        cancelado.valor_aberto = Decimal('500.00')
        cancelado.save()
        data = relatorio_contas_receber({'incluir_cancelados': '1'})
        aberto_card = Decimal(data['cards']['total_aberto']['valor'])
        self.assertEqual(aberto_card, Decimal('200.00'))

    def test_relatorio_nao_altera_titulo(self):
        titulo = self._criar_receber()
        saldo_antes = titulo.valor_aberto
        status_antes = titulo.status
        relatorio_contas_receber({})
        relatorio_clientes({})
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, saldo_antes)
        self.assertEqual(titulo.status, status_antes)
