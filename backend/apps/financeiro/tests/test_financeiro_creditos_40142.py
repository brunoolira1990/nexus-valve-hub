"""Testes ERP 4.0.14.2 — créditos, abatimentos e aplicação operacional."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro
from apps.financeiro.models import ContaFinanceira, CreditoFinanceiro, TituloFinanceiro
from apps.financeiro.services.baixa import estornar_baixa_financeira, registrar_baixa_financeira
from apps.financeiro.services.credito import (
    CreditoFinanceiroError,
    aplicar_credito_em_titulo,
    criar_credito_financeiro,
)
from apps.financeiro.services.movimento import registrar_abatimento_devolucao
from apps.financeiro.services.titulo import cancelar_titulo_financeiro, criar_titulo_financeiro


class FinanceiroCreditos40142Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin_40142', 'fin40142@test.com', 'x')
        self.cliente_a = Cliente.objects.create(razao_social='Cliente A', cnpj='39053344705')
        self.cliente_b = Cliente.objects.create(razao_social='Cliente B', cnpj='59443075000120')
        self.fornecedor_a = Fornecedor.objects.create(razao_social='Fornecedor A', cnpj='11222333000181')
        self.fornecedor_b = Fornecedor.objects.create(razao_social='Fornecedor B', cnpj='22333444000182')
        self.conta = ContaFinanceira.objects.create(nome='Conta Teste', tipo='CAIXA')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_criar_credito_cliente(self):
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente_a.pk,
            valor_original=Decimal('500.00'),
            data_credito=date.today(),
            motivo='Ajuste manual',
            usuario=self.user,
        )
        self.assertEqual(credito.saldo, Decimal('500.00'))
        self.assertEqual(credito.status, CreditoFinanceiro.Status.DISPONIVEL)

    def test_criar_credito_fornecedor(self):
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.FORNECEDOR,
            fornecedor_id=self.fornecedor_a.pk,
            valor_original=Decimal('300.00'),
            data_credito=date.today(),
            motivo='Devolução parcial',
            usuario=self.user,
        )
        self.assertEqual(credito.tipo, CreditoFinanceiro.Tipo.FORNECEDOR)

    def test_bloqueia_credito_cliente_sem_cliente(self):
        with self.assertRaises(CreditoFinanceiroError):
            criar_credito_financeiro(
                tipo=CreditoFinanceiro.Tipo.CLIENTE,
                valor_original=Decimal('100.00'),
                data_credito=date.today(),
                motivo='Teste',
                usuario=self.user,
            )

    def test_bloqueia_credito_fornecedor_sem_fornecedor(self):
        with self.assertRaises(CreditoFinanceiroError):
            criar_credito_financeiro(
                tipo=CreditoFinanceiro.Tipo.FORNECEDOR,
                valor_original=Decimal('100.00'),
                data_credito=date.today(),
                motivo='Teste',
                usuario=self.user,
            )

    def test_aplicar_credito_cliente_mesmo_cliente(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('400.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente_a.pk,
            valor_original=Decimal('200.00'),
            data_credito=date.today(),
            motivo='Crédito teste',
            usuario=self.user,
        )
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('120.00'),
            data_aplicacao=date.today(),
            motivo='Uso parcial',
            usuario=self.user,
        )
        credito.refresh_from_db()
        titulo.refresh_from_db()
        self.assertEqual(credito.saldo, Decimal('80.00'))
        self.assertEqual(titulo.valor_aberto, Decimal('280.00'))

    def test_bloqueia_credito_cliente_outro_cliente(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_b.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('400.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente_a.pk,
            valor_original=Decimal('200.00'),
            data_credito=date.today(),
            motivo='Crédito teste',
            usuario=self.user,
        )
        with self.assertRaises(CreditoFinanceiroError):
            aplicar_credito_em_titulo(
                credito,
                titulo,
                valor=Decimal('50.00'),
                data_aplicacao=date.today(),
                motivo='Tentativa inválida',
                usuario=self.user,
            )

    def test_aplicar_credito_fornecedor_mesmo_fornecedor(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('600.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.FORNECEDOR,
            fornecedor_id=self.fornecedor_a.pk,
            valor_original=Decimal('250.00'),
            data_credito=date.today(),
            motivo='Crédito fornecedor',
            usuario=self.user,
        )
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('100.00'),
            data_aplicacao=date.today(),
            motivo='Compensação',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, Decimal('500.00'))

    def test_bloqueia_credito_fornecedor_outro_fornecedor(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_b.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('600.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.FORNECEDOR,
            fornecedor_id=self.fornecedor_a.pk,
            valor_original=Decimal('250.00'),
            data_credito=date.today(),
            motivo='Crédito fornecedor',
            usuario=self.user,
        )
        with self.assertRaises(CreditoFinanceiroError):
            aplicar_credito_em_titulo(
                credito,
                titulo,
                valor=Decimal('50.00'),
                data_aplicacao=date.today(),
                motivo='Inválido',
                usuario=self.user,
            )

    def test_aplicacao_total_quita_titulo(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('150.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente_a.pk,
            valor_original=Decimal('200.00'),
            data_credito=date.today(),
            motivo='Crédito',
            usuario=self.user,
        )
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('150.00'),
            data_aplicacao=date.today(),
            motivo='Quitação',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        self.assertLessEqual(titulo.valor_aberto, Decimal('0.01'))
        self.assertEqual(titulo.status, TituloFinanceiro.Status.RECEBIDO)

    def test_abatimento_receber(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('350.00'),
            usuario=self.user,
        )
        bx = registrar_abatimento_devolucao(
            titulo,
            valor=Decimal('80.00'),
            data_abatimento=date.today(),
            motivo='Devolução parcial',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        self.assertEqual(bx.tipo_movimento, TipoMovimentoFinanceiro.ABATIMENTO_DEVOLUCAO)
        self.assertEqual(titulo.valor_aberto, Decimal('270.00'))

    def test_abatimento_pagar(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('350.00'),
            usuario=self.user,
        )
        registrar_abatimento_devolucao(
            titulo,
            valor=Decimal('50.00'),
            data_abatimento=date.today(),
            motivo='Devolução',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, Decimal('300.00'))

    def test_bloqueia_abatimento_maior_que_saldo(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('100.00'),
            usuario=self.user,
        )
        with self.assertRaises(Exception):
            registrar_abatimento_devolucao(
                titulo,
                valor=Decimal('150.00'),
                data_abatimento=date.today(),
                motivo='Excesso',
                usuario=self.user,
            )

    def test_estornar_uso_credito_reabre_saldos(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('300.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente_a.pk,
            valor_original=Decimal('200.00'),
            data_credito=date.today(),
            motivo='Crédito',
            usuario=self.user,
        )
        bx = aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('120.00'),
            data_aplicacao=date.today(),
            motivo='Uso',
            usuario=self.user,
        )
        estornar_baixa_financeira(bx, motivo='Estorno teste', usuario=self.user)
        credito.refresh_from_db()
        titulo.refresh_from_db()
        self.assertEqual(credito.saldo, Decimal('200.00'))
        self.assertEqual(titulo.valor_aberto, Decimal('300.00'))

    def test_estornar_abatimento_reabre_titulo(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('400.00'),
            usuario=self.user,
        )
        bx = registrar_abatimento_devolucao(
            titulo,
            valor=Decimal('90.00'),
            data_abatimento=date.today(),
            motivo='Devolução',
            usuario=self.user,
        )
        estornar_baixa_financeira(bx, motivo='Erro', usuario=self.user)
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, Decimal('400.00'))

    def test_bloqueia_estorno_duplicado(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('200.00'),
            usuario=self.user,
        )
        bx = registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=Decimal('200.00'),
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.PIX,
            usuario=self.user,
        )
        estornar_baixa_financeira(bx, motivo='Primeiro', usuario=self.user)
        with self.assertRaises(Exception):
            estornar_baixa_financeira(bx, motivo='Segundo', usuario=self.user)

    def test_titulo_cancelado_nao_aceita_credito(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('200.00'),
            usuario=self.user,
        )
        cancelar_titulo_financeiro(titulo, motivo='Cancelado', usuario=self.user)
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente_a.pk,
            valor_original=Decimal('100.00'),
            data_credito=date.today(),
            motivo='Crédito',
            usuario=self.user,
        )
        with self.assertRaises(CreditoFinanceiroError):
            aplicar_credito_em_titulo(
                credito,
                titulo,
                valor=Decimal('50.00'),
                data_aplicacao=date.today(),
                motivo='Tentativa',
                usuario=self.user,
            )

    def test_titulo_cancelado_nao_aceita_abatimento(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('200.00'),
            usuario=self.user,
        )
        cancelar_titulo_financeiro(titulo, motivo='Cancelado', usuario=self.user)
        with self.assertRaises(Exception):
            registrar_abatimento_devolucao(
                titulo,
                valor=Decimal('50.00'),
                data_abatimento=date.today(),
                motivo='Tentativa',
                usuario=self.user,
            )

    def test_api_criar_credito_cliente(self):
        resp = self.api.post(
            '/api/financeiro/creditos/',
            {
                'tipo': 'CLIENTE',
                'cliente': self.cliente_a.pk,
                'valor_original': '750.00',
                'data_credito': str(date.today()),
                'motivo': 'API teste',
                'origem_tipo': 'MANUAL',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['pode_aplicar'], True)

    def test_api_abater_devolucao_receber(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente_a.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('500.00'),
            usuario=self.user,
        )
        resp = self.api.post(
            f'/api/financeiro/contas-receber/{titulo.pk}/abater-devolucao/',
            {
                'data': str(date.today()),
                'valor': '100.00',
                'motivo': 'Devolução API',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.json()['titulo']['valor_aberto']), Decimal('400.00'))
