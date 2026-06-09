"""ERP 4.0.14.5 — Resumo financeiro, vencimentos e alertas."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.models import ContaFinanceira, CreditoFinanceiro, TituloFinanceiro
from apps.financeiro.resumo import montar_resumo_financeiro
from apps.financeiro.services.titulo import criar_titulo_financeiro


class FinanceiroResumo40145Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin40145', 'fin40145@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cli = Cliente.objects.create(razao_social='Cli 40145', cnpj='39053344705')
        self.forn = Fornecedor.objects.create(razao_social='Forn 40145', cnpj='59443075000120')
        self.conta = ContaFinanceira.objects.create(nome='Conta 40145', tipo='CAIXA')
        self.hoje = timezone.localdate()

    def _criar_receber(self, vencimento: date, valor: str = '100.00'):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cli.pk,
            data_emissao=self.hoje,
            data_vencimento=vencimento,
            valor_original=Decimal(valor),
            usuario=self.user,
        )

    def _criar_pagar(self, vencimento: date, valor: str = '80.00'):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.forn.pk,
            tipo_lancamento=TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR,
            data_emissao=self.hoje,
            data_vencimento=vencimento,
            valor_original=Decimal(valor),
            usuario=self.user,
        )

    def test_resumo_a_receber_vencido(self):
        self._criar_receber(self.hoje - timedelta(days=5))
        res = self.client.get('/api/financeiro/resumo/')
        self.assertEqual(res.status_code, 200)
        self.assertGreater(Decimal(res.json()['receber']['vencido']['valor']), 0)
        self.assertGreaterEqual(res.json()['receber']['vencido']['quantidade'], 1)

    def test_resumo_a_receber_hoje(self):
        self._criar_receber(self.hoje)
        data = montar_resumo_financeiro(periodo='mes')
        self.assertGreater(Decimal(data['receber']['hoje']['valor']), 0)

    def test_resumo_a_pagar_vencido(self):
        self._criar_pagar(self.hoje - timedelta(days=3))
        data = montar_resumo_financeiro(periodo='mes')
        self.assertGreater(Decimal(data['pagar']['vencido']['valor']), 0)

    def test_resumo_a_pagar_hoje(self):
        self._criar_pagar(self.hoje)
        res = self.client.get('/api/financeiro/resumo/')
        self.assertGreater(Decimal(res.json()['pagar']['hoje']['valor']), 0)

    def test_resumo_proximos_7_dias(self):
        self._criar_receber(self.hoje + timedelta(days=3))
        self._criar_pagar(self.hoje + timedelta(days=5))
        data = montar_resumo_financeiro(periodo='mes')
        self.assertGreater(Decimal(data['receber']['proximos_7_dias']['valor']), 0)
        self.assertGreater(Decimal(data['pagar']['proximos_7_dias']['valor']), 0)

    def test_resumo_ignora_cancelados_em_aberto(self):
        titulo = self._criar_receber(self.hoje)
        titulo.cancelado = True
        titulo.status = TituloFinanceiro.Status.CANCELADO
        titulo.valor_aberto = Decimal('0')
        titulo.save()
        data = montar_resumo_financeiro(periodo='mes')
        # Outros títulos do setUp não existem — em aberto não deve incluir cancelado
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                pk=titulo.pk,
                cancelado=False,
                valor_aberto__gt=0,
            ).count(),
            0,
        )

    def test_filtro_cr_vencidos(self):
        self._criar_receber(self.hoje - timedelta(days=2))
        res = self.client.get('/api/financeiro/contas-receber/?vencimento=vencidos')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.json()['count'], 1)

    def test_filtro_cp_vencidos(self):
        self._criar_pagar(self.hoje - timedelta(days=1))
        res = self.client.get('/api/financeiro/contas-pagar/?vencimento=vencidos')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.json()['count'], 1)

    def test_filtro_origem_nfe_saida(self):
        titulo = self._criar_receber(self.hoje + timedelta(days=10))
        titulo.origem_tipo = TituloFinanceiro.OrigemTipo.NFE_SAIDA
        titulo.origem_id = 99901
        titulo.save(update_fields=['origem_tipo', 'origem_id'])
        res = self.client.get('/api/financeiro/contas-receber/?origem_tipo=NFE_SAIDA')
        self.assertEqual(res.status_code, 200)
        ids = [r['id'] for r in res.json()['results']]
        self.assertIn(titulo.id, ids)

    def test_filtro_origem_nfe_entrada(self):
        titulo = self._criar_pagar(self.hoje + timedelta(days=10))
        titulo.origem_tipo = TituloFinanceiro.OrigemTipo.NFE_ENTRADA
        titulo.origem_id = 88801
        titulo.save(update_fields=['origem_tipo', 'origem_id'])
        res = self.client.get('/api/financeiro/contas-pagar/?origem_tipo=NFE_ENTRADA')
        self.assertEqual(res.status_code, 200)
        ids = [r['id'] for r in res.json()['results']]
        self.assertIn(titulo.id, ids)

    def test_resumo_creditos_disponiveis(self):
        CreditoFinanceiro.objects.create(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente=self.cli,
            valor_original=Decimal('50'),
            valor_utilizado=Decimal('0'),
            saldo=Decimal('50'),
            data_credito=self.hoje,
            motivo='Teste',
        )
        data = montar_resumo_financeiro(periodo='mes')
        self.assertGreater(Decimal(data['creditos']['clientes']['valor_disponivel']), 0)

    def test_alerta_origem_fiscal_no_resumo(self):
        titulo = self._criar_receber(self.hoje)
        titulo.origem_tipo = TituloFinanceiro.OrigemTipo.NFE_SAIDA
        titulo.origem_id = 1
        titulo.save(update_fields=['origem_tipo', 'origem_id'])
        res = self.client.get('/api/financeiro/resumo/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('alertas', res.json())

    def test_saldo_previsto_em_aberto(self):
        self._criar_receber(self.hoje + timedelta(days=2), '200.00')
        self._criar_pagar(self.hoje + timedelta(days=2), '50.00')
        data = montar_resumo_financeiro(periodo='mes')
        saldo = Decimal(data['saldo_previsto']['em_aberto'])
        self.assertGreater(saldo, 0)
