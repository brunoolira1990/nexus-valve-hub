"""Testes ERP 4.0.14.2.2 — exclusão segura após estorno."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.constants import FormaPagamentoCodigo
from apps.financeiro.models import ContaFinanceira, CreditoFinanceiro, TituloFinanceiro
from apps.financeiro.services.baixa import estornar_baixa_financeira, registrar_baixa_financeira
from apps.financeiro.services.credito import (
    CreditoFinanceiroError,
    aplicar_credito_em_titulo,
    criar_credito_financeiro,
    excluir_credito_financeiro,
)
from apps.financeiro.services.movimento import registrar_abatimento_devolucao
from apps.financeiro.services.titulo import criar_titulo_financeiro, excluir_titulo_financeiro


class FinanceiroExclusao401422Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin_401422', 'fin401422@test.com', 'x')
        self.cliente = Cliente.objects.create(razao_social='Cliente 422', cnpj='39053344705')
        self.fornecedor = Fornecedor.objects.create(razao_social='Fornec 422', cnpj='11222333000181')
        self.conta = ContaFinanceira.objects.create(nome='Conta 422', tipo='CAIXA')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

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

    def _credito_manual(self, valor='500.00'):
        return criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente.pk,
            valor_original=Decimal(valor),
            data_credito=date.today(),
            motivo='Crédito manual',
            origem_tipo=CreditoFinanceiro.OrigemTipo.MANUAL,
            usuario=self.user,
        )

    def test_titulo_manual_sem_movimento_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        pk = titulo.pk
        excluir_titulo_financeiro(titulo, motivo='Erro de cadastro manual', usuario=self.user)
        self.assertFalse(TituloFinanceiro.objects.filter(pk=pk).exists())

    def test_titulo_manual_com_baixa_ativa_nao_pode_ser_excluido(self):
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
        with self.assertRaises(ValueError) as ctx:
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)
        self.assertIn('ativas', str(ctx.exception).lower())

    def test_titulo_manual_com_baixa_estornada_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        baixa = registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=Decimal('100.00'),
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.PIX,
            usuario=self.user,
        )
        estornar_baixa_financeira(baixa, motivo='Estorno operacional teste', usuario=self.user)
        titulo.refresh_from_db()
        pk = titulo.pk
        excluir_titulo_financeiro(titulo, motivo='Correção após estorno', usuario=self.user)
        self.assertFalse(TituloFinanceiro.objects.filter(pk=pk).exists())

    def test_titulo_manual_com_uso_credito_ativo_nao_pode_ser_excluido(self):
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

    def test_titulo_manual_com_uso_credito_estornado_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        baixa = aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('80.00'),
            data_aplicacao=date.today(),
            motivo='Uso teste',
            usuario=self.user,
        )
        estornar_baixa_financeira(baixa, motivo='Estorno uso crédito', usuario=self.user)
        titulo.refresh_from_db()
        pk = titulo.pk
        excluir_titulo_financeiro(titulo, motivo='Correção após estorno crédito', usuario=self.user)
        self.assertFalse(TituloFinanceiro.objects.filter(pk=pk).exists())

    def test_titulo_manual_com_abatimento_ativo_nao_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        registrar_abatimento_devolucao(
            titulo,
            valor=Decimal('50.00'),
            data_abatimento=date.today(),
            motivo='Devolução parcial',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)

    def test_titulo_manual_com_abatimento_estornado_pode_ser_excluido(self):
        titulo = self._titulo_manual()
        baixa = registrar_abatimento_devolucao(
            titulo,
            valor=Decimal('50.00'),
            data_abatimento=date.today(),
            motivo='Devolução parcial',
            usuario=self.user,
        )
        estornar_baixa_financeira(baixa, motivo='Estorno abatimento', usuario=self.user)
        titulo.refresh_from_db()
        pk = titulo.pk
        excluir_titulo_financeiro(titulo, motivo='Correção após abatimento estornado', usuario=self.user)
        self.assertFalse(TituloFinanceiro.objects.filter(pk=pk).exists())

    def test_titulo_origem_nfe_nao_pode_ser_excluido(self):
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
        with self.assertRaises(ValueError) as ctx:
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)
        self.assertIn('documento', str(ctx.exception).lower())

    def test_titulo_origem_pedido_nao_pode_ser_excluido(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('300.00'),
            origem_tipo=TituloFinanceiro.OrigemTipo.PEDIDO_VENDA,
            origem_id=123,
            usuario=self.user,
        )
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa inválida', usuario=self.user)

    def test_credito_manual_sem_movimento_pode_ser_excluido(self):
        credito = self._credito_manual()
        excluir_credito_financeiro(credito, motivo='Erro cadastro', usuario=self.user)
        self.assertFalse(CreditoFinanceiro.objects.filter(pk=credito.pk).exists())

    def test_credito_com_aplicacao_ativa_nao_pode_ser_excluido(self):
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

    def test_credito_com_aplicacao_estornada_pode_ser_excluido(self):
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
        estornar_baixa_financeira(baixa, motivo='Estorno uso crédito', usuario=self.user)
        credito.refresh_from_db()
        excluir_credito_financeiro(credito, motivo='Correção após estorno', usuario=self.user)
        self.assertFalse(CreditoFinanceiro.objects.filter(pk=credito.pk).exists())

    def test_credito_origem_devolucao_nao_pode_ser_excluido(self):
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente.pk,
            valor_original=Decimal('200.00'),
            data_credito=date.today(),
            motivo='Devolução',
            origem_tipo=CreditoFinanceiro.OrigemTipo.DEVOLUCAO,
            usuario=self.user,
        )
        with self.assertRaises(CreditoFinanceiroError):
            excluir_credito_financeiro(credito, motivo='Tentativa inválida', usuario=self.user)

    def test_exclusao_exige_motivo(self):
        credito = self._credito_manual()
        with self.assertRaises(CreditoFinanceiroError):
            excluir_credito_financeiro(credito, motivo='', usuario=self.user)

    def test_api_retorna_motivo_bloqueio_amigavel(self):
        titulo = self._titulo_manual()
        credito = self._credito_manual()
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('50.00'),
            data_aplicacao=date.today(),
            motivo='Uso parcial',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        credito.refresh_from_db()
        res_t = self.api.get(f'/api/financeiro/contas-receber/{titulo.pk}/')
        res_c = self.api.get(f'/api/financeiro/creditos/{credito.pk}/')
        self.assertFalse(res_t.data['pode_excluir'])
        self.assertFalse(res_c.data['pode_excluir'])
        self.assertTrue(res_t.data['motivo_bloqueio_exclusao'])
        self.assertTrue(res_c.data['motivo_bloqueio_exclusao'])

    def test_flags_apos_estorno_permitem_exclusao(self):
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
        estornar_baixa_financeira(baixa, motivo='Estorno completo', usuario=self.user)
        titulo.refresh_from_db()
        credito.refresh_from_db()
        res_t = self.api.get(f'/api/financeiro/contas-receber/{titulo.pk}/')
        res_c = self.api.get(f'/api/financeiro/creditos/{credito.pk}/')
        self.assertTrue(res_t.data['pode_excluir'])
        self.assertTrue(res_c.data['pode_excluir'])
        self.assertTrue(res_t.data['possui_apenas_movimentos_estornados'])
        self.assertTrue(res_c.data['possui_apenas_movimentos_estornados'])
