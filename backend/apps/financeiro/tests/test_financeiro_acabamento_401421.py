"""Testes ERP 4.0.14.2.1 — acabamento operacional de créditos e exclusão segura."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.constants import FormaPagamentoCodigo
from apps.financeiro.models import ContaFinanceira, CreditoFinanceiro, CreditoFinanceiroEvento, TituloFinanceiro
from apps.financeiro.services.baixa import estornar_baixa_financeira, registrar_baixa_financeira
from apps.financeiro.services.credito import (
    CreditoFinanceiroError,
    aplicar_credito_em_titulo,
    atualizar_credito_financeiro,
    cancelar_credito_financeiro,
    criar_credito_financeiro,
    excluir_credito_financeiro,
)
from apps.financeiro.services.titulo import criar_titulo_financeiro, excluir_titulo_financeiro


class FinanceiroAcabamento401421Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin_401421', 'fin401421@test.com', 'x')
        self.cliente = Cliente.objects.create(razao_social='Cliente Acab', cnpj='39053344705')
        self.fornecedor = Fornecedor.objects.create(razao_social='Fornec Acab', cnpj='11222333000181')
        self.conta = ContaFinanceira.objects.create(nome='Conta Acab', tipo='CAIXA')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _credito_manual(self, valor='500.00'):
        return criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente.pk,
            valor_original=Decimal(valor),
            data_credito=date.today(),
            motivo='Crédito manual teste',
            origem_tipo=CreditoFinanceiro.OrigemTipo.MANUAL,
            usuario=self.user,
        )

    def _titulo_manual(self, valor='400.00'):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal(valor),
            origem_tipo=TituloFinanceiro.OrigemTipo.MANUAL,
            usuario=self.user,
        )

    def test_credito_manual_disponivel_pode_ser_excluido(self):
        credito = self._credito_manual()
        excluir_credito_financeiro(credito, motivo='Erro de cadastro operacional', usuario=self.user)
        self.assertFalse(CreditoFinanceiro.objects.filter(pk=credito.pk).exists())

    def test_credito_com_aplicacao_nao_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('100.00'),
            data_aplicacao=date.today(),
            motivo='Uso teste',
            usuario=self.user,
        )
        credito.refresh_from_db()
        with self.assertRaises(CreditoFinanceiroError):
            excluir_credito_financeiro(credito, motivo='Tentativa inválida', usuario=self.user)

    def test_credito_com_estorno_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        baixa = aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('100.00'),
            data_aplicacao=date.today(),
            motivo='Uso teste',
            usuario=self.user,
        )
        estornar_baixa_financeira(baixa, motivo='Estorno operacional teste', usuario=self.user)
        credito.refresh_from_db()
        excluir_credito_financeiro(credito, motivo='Correção após estorno', usuario=self.user)
        self.assertFalse(CreditoFinanceiro.objects.filter(pk=credito.pk).exists())

    def test_credito_cancelado_nao_pode_ser_aplicado(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        cancelar_credito_financeiro(credito, motivo='Cancelamento operacional', usuario=self.user)
        credito.refresh_from_db()
        with self.assertRaises(CreditoFinanceiroError):
            aplicar_credito_em_titulo(
                credito,
                titulo,
                valor=Decimal('50.00'),
                data_aplicacao=date.today(),
                motivo='Tentativa',
                usuario=self.user,
            )

    def test_credito_sem_movimento_edicao_completa(self):
        credito = self._credito_manual()
        atualizado = atualizar_credito_financeiro(
            credito,
            valor_original=Decimal('750.00'),
            origem_numero='DOC-001',
            motivo='Motivo revisado',
            usuario=self.user,
        )
        self.assertEqual(atualizado.valor_original, Decimal('750.00'))
        self.assertEqual(atualizado.origem_numero, 'DOC-001')

    def test_credito_com_movimento_bloqueia_valor(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('100.00'),
            data_aplicacao=date.today(),
            motivo='Uso teste',
            usuario=self.user,
        )
        credito.refresh_from_db()
        with self.assertRaises(CreditoFinanceiroError) as ctx:
            atualizar_credito_financeiro(credito, valor_original=Decimal('900.00'), usuario=self.user)
        self.assertIn('movimentações', str(ctx.exception).lower())

    def test_credito_com_movimento_permite_observacoes(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('100.00'),
            data_aplicacao=date.today(),
            motivo='Uso teste',
            usuario=self.user,
        )
        credito.refresh_from_db()
        atualizado = atualizar_credito_financeiro(
            credito,
            observacoes='Observação complementar após uso',
            origem_numero='REF-99',
            usuario=self.user,
        )
        self.assertEqual(atualizado.observacoes, 'Observação complementar após uso')
        self.assertEqual(atualizado.origem_numero, 'REF-99')

    def test_cancelar_credito_exige_motivo(self):
        credito = self._credito_manual()
        with self.assertRaises(CreditoFinanceiroError):
            cancelar_credito_financeiro(credito, motivo='', usuario=self.user)

    def test_titulo_manual_sem_movimento_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        pk = titulo.pk
        excluir_titulo_financeiro(titulo, motivo='Erro de cadastro manual', usuario=self.user)
        self.assertFalse(TituloFinanceiro.objects.filter(pk=pk).exists())

    def test_titulo_manual_com_baixa_nao_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=Decimal('100.00'),
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.PIX,
            usuario=self.user,
        )
        titulo.refresh_from_db()
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)

    def test_titulo_manual_com_credito_aplicado_nao_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('80.00'),
            data_aplicacao=date.today(),
            motivo='Uso teste',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)

    def test_titulo_com_origem_nfe_nao_pode_ser_excluido(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('300.00'),
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
            origem_id=999,
            usuario=self.user,
        )
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)

    def test_exclusao_exige_motivo(self):
        credito = self._credito_manual()
        with self.assertRaises(CreditoFinanceiroError):
            excluir_credito_financeiro(credito, motivo='', usuario=self.user)

    def test_cancelamento_preserva_historico(self):
        credito = self._credito_manual()
        cancelar_credito_financeiro(credito, motivo='Cancelamento com histórico', usuario=self.user)
        credito.refresh_from_db()
        self.assertTrue(credito.cancelado)
        self.assertTrue(
            credito.eventos.filter(acao=CreditoFinanceiroEvento.Acao.CANCELAMENTO).exists(),
        )

    def test_api_excluir_credito_com_motivo(self):
        credito = self._credito_manual()
        res = self.api.post(
            f'/api/financeiro/creditos/{credito.pk}/excluir/',
            {'motivo': 'Correção de lançamento duplicado'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('excluído', res.data['mensagem'].lower())

    def test_api_flags_credito_pode_excluir(self):
        credito = self._credito_manual()
        res = self.api.get(f'/api/financeiro/creditos/{credito.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['pode_excluir'])
        self.assertTrue(res.data['pode_editar_completo'])

    def test_api_titulo_flags_pode_excluir(self):
        titulo = self._titulo_manual()
        res = self.api.get(f'/api/financeiro/contas-receber/{titulo.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['pode_excluir'])
        self.assertTrue(res.data['origem_manual'])
