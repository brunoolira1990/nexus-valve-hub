"""Testes financeiro operacional — banco isolado, sem dados visíveis no app."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro
from apps.financeiro.models import ContaFinanceira, CreditoFinanceiro, TituloFinanceiro
from apps.financeiro.services.baixa import estornar_baixa_financeira, registrar_baixa_financeira
from apps.financeiro.services.credito import aplicar_credito_em_titulo, criar_credito_financeiro
from apps.financeiro.services.movimento import registrar_abatimento_devolucao
from apps.financeiro.services.titulo import criar_titulo_financeiro


class FinanceiroOperacionalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin_test', 'fin@test.com', 'x')
        self.cliente = Cliente.objects.create(razao_social='Cliente Teste', cnpj='39053344705')
        self.fornecedor = Fornecedor.objects.create(razao_social='Fornecedor Teste', cnpj='59443075000120')
        self.conta = ContaFinanceira.objects.create(nome='Conta Teste', tipo='CAIXA')

    def test_forma_pagamento_fixa_em_baixa(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today(),
            valor_original=Decimal('500.00'),
            usuario=self.user,
        )
        bx = registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=Decimal('500.00'),
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.PIX,
            usuario=self.user,
        )
        self.assertEqual(bx.forma_pagamento_codigo, FormaPagamentoCodigo.PIX)

    def test_credito_cliente_aplicar_e_estornar(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=20),
            valor_original=Decimal('300.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.CLIENTE,
            cliente_id=self.cliente.pk,
            valor_original=Decimal('200.00'),
            data_credito=date.today(),
            motivo='Devolução manual',
            usuario=self.user,
        )
        bx = aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('120.00'),
            data_aplicacao=date.today(),
            motivo='Uso parcial',
            usuario=self.user,
        )
        credito.refresh_from_db(); titulo.refresh_from_db()
        self.assertEqual(bx.tipo_movimento, TipoMovimentoFinanceiro.USO_CREDITO)
        self.assertEqual(credito.saldo, Decimal('80.00'))
        self.assertEqual(titulo.valor_aberto, Decimal('180.00'))

        estornar_baixa_financeira(bx, motivo='Estorno teste', usuario=self.user)
        credito.refresh_from_db(); titulo.refresh_from_db()
        self.assertEqual(credito.saldo, Decimal('200.00'))
        self.assertEqual(titulo.valor_aberto, Decimal('300.00'))

    def test_credito_fornecedor_em_pagar(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=20),
            valor_original=Decimal('400.00'),
            usuario=self.user,
        )
        credito = criar_credito_financeiro(
            tipo=CreditoFinanceiro.Tipo.FORNECEDOR,
            fornecedor_id=self.fornecedor.pk,
            valor_original=Decimal('150.00'),
            data_credito=date.today(),
            motivo='Ajuste manual',
            usuario=self.user,
        )
        aplicar_credito_em_titulo(
            credito,
            titulo,
            valor=Decimal('100.00'),
            data_aplicacao=date.today(),
            motivo='Compensação parcial',
            usuario=self.user,
        )
        credito.refresh_from_db(); titulo.refresh_from_db()
        self.assertEqual(credito.saldo, Decimal('50.00'))
        self.assertEqual(titulo.valor_aberto, Decimal('300.00'))

    def test_abatimento_devolucao_e_estorno(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=20),
            valor_original=Decimal('400.00'),
            usuario=self.user,
        )
        bx = registrar_abatimento_devolucao(
            titulo,
            valor=Decimal('90.00'),
            data_abatimento=date.today(),
            motivo='Devolução parcial',
            usuario=self.user,
        )
        titulo.refresh_from_db()
        self.assertEqual(bx.forma_pagamento_codigo, FormaPagamentoCodigo.SEM_MOVIMENTACAO_FINANCEIRA)
        self.assertEqual(titulo.valor_aberto, Decimal('310.00'))

        estornar_baixa_financeira(bx, motivo='Erro lançamento', usuario=self.user)
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, Decimal('400.00'))

    def test_api_formas_pagamento_legado_inexistente(self):
        self.client.force_login(self.user)
        resp = self.client.get('/api/financeiro/formas-pagamento/')
        self.assertEqual(resp.status_code, 404)

    def test_conta_banco_exige_banco_no_serializer(self):
        from apps.financeiro.serializers import ContaFinanceiraSerializer

        ser = ContaFinanceiraSerializer(data={'nome': 'Conta sem banco', 'tipo': 'BANCO', 'banco': ''})
        self.assertFalse(ser.is_valid())
        self.assertIn('banco', ser.errors)

    def test_conta_banco_aceita_banco(self):
        from apps.financeiro.serializers import ContaFinanceiraSerializer

        ser = ContaFinanceiraSerializer(
            data={'nome': 'Conta Itaú principal', 'tipo': 'BANCO', 'banco': 'Itaú', 'agencia': '1234'},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        conta = ser.save()
        self.assertEqual(conta.banco, 'Itaú')
        self.assertEqual(conta.agencia, '1234')

    def test_conta_caixa_nao_exige_banco(self):
        from apps.financeiro.serializers import ContaFinanceiraSerializer

        ser = ContaFinanceiraSerializer(data={'nome': 'Caixa loja', 'tipo': 'CAIXA'})
        self.assertTrue(ser.is_valid(), ser.errors)
        conta = ser.save()
        self.assertEqual(conta.banco, '')

    def test_api_conta_banco_retorna_banco(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(
            '/api/financeiro/contas/',
            {'nome': 'Conta API', 'tipo': 'BANCO', 'banco': 'Bradesco'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['banco'], 'Bradesco')

    def test_titulo_serializer_flags_em_aberto(self):
        from apps.financeiro.serializers import TituloFinanceiroSerializer

        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('1500.00'),
            usuario=self.user,
        )
        data = TituloFinanceiroSerializer(titulo).data
        self.assertGreater(Decimal(data['valor_aberto']), Decimal('0'))
        self.assertTrue(data['pode_baixar'])
        self.assertTrue(data['pode_editar'])
        self.assertTrue(data['pode_cancelar'])
        self.assertFalse(data['possui_baixa_ativa'])
        self.assertFalse(data['pode_estornar_baixa'])

    def test_titulo_serializer_flags_parcial(self):
        from apps.financeiro.serializers import TituloFinanceiroSerializer

        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=10),
            valor_original=Decimal('5000.00'),
            usuario=self.user,
        )
        registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=Decimal('2000.00'),
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.PIX,
            usuario=self.user,
        )
        titulo.refresh_from_db()
        data = TituloFinanceiroSerializer(titulo, context={'detail': True}).data
        self.assertGreater(Decimal(data['valor_aberto']), Decimal('0'))
        self.assertTrue(data['possui_baixa_ativa'])
        self.assertTrue(data['pode_estornar_baixa'])
        self.assertTrue(data['pode_baixar'])

    def test_titulo_serializer_flags_quitado(self):
        from apps.financeiro.serializers import TituloFinanceiroSerializer

        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=date.today(),
            data_vencimento=date.today(),
            valor_original=Decimal('800.00'),
            usuario=self.user,
        )
        registrar_baixa_financeira(
            titulo,
            data_baixa=date.today(),
            valor=Decimal('800.00'),
            conta_financeira_id=self.conta.pk,
            forma_pagamento_codigo=FormaPagamentoCodigo.PIX,
            usuario=self.user,
        )
        titulo.refresh_from_db()
        data = TituloFinanceiroSerializer(titulo).data
        self.assertLessEqual(Decimal(data['valor_aberto']), Decimal('0.01'))
        self.assertFalse(data['pode_baixar'])
        self.assertTrue(data['possui_baixa_ativa'])
        self.assertTrue(data['pode_estornar_baixa'])

    def test_titulo_serializer_flags_cancelado(self):
        from apps.financeiro.serializers import TituloFinanceiroSerializer
        from apps.financeiro.services.titulo import cancelar_titulo_financeiro

        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            fornecedor_id=self.fornecedor.pk,
            data_emissao=date.today(),
            data_vencimento=date.today() + timedelta(days=5),
            valor_original=Decimal('300.00'),
            usuario=self.user,
        )
        cancelar_titulo_financeiro(titulo, motivo='Teste cancelamento', usuario=self.user)
        titulo.refresh_from_db()
        data = TituloFinanceiroSerializer(titulo).data
        self.assertFalse(data['pode_baixar'])
        self.assertFalse(data['pode_abater'])
        self.assertFalse(data['pode_aplicar_credito'])
        self.assertEqual(data['status'], TituloFinanceiro.Status.CANCELADO)
