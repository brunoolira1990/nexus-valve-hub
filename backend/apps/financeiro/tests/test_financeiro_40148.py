"""ERP 4.0.14.8 — numeração CR/CP, vencimento em relatórios/PDF."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.financeiro.models import ParcelaFinanceira, TituloFinanceiro
from apps.financeiro.relatorios import relatorio_contas_receber
from apps.financeiro.relatorios_pdf import pdf_relatorio_contas_receber
from apps.financeiro.services.titulo import criar_titulo_financeiro, gerar_numero_titulo_financeiro
from apps.financeiro.vencimento_exibicao import vencimento_exibicao_titulo


class FinanceiroNumeracao40148Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('num40148', 'num40148@test.com', 'x')
        self.cliente = Cliente.objects.create(razao_social='Cli 40148', cnpj='39053344709')
        self.hoje = timezone.localdate()

    def test_cr_gera_padrao_ano(self):
        n = gerar_numero_titulo_financeiro(TituloFinanceiro.Tipo.RECEBER, self.hoje)
        self.assertRegex(n, rf'^CR-{self.hoje.year}-\d{{6}}$')

    def test_cp_gera_padrao_ano(self):
        n = gerar_numero_titulo_financeiro(TituloFinanceiro.Tipo.PAGAR, self.hoje)
        self.assertRegex(n, rf'^CP-{self.hoje.year}-\d{{6}}$')

    def test_sequenciais_independentes_cr_cp(self):
        cr = gerar_numero_titulo_financeiro(TituloFinanceiro.Tipo.RECEBER, self.hoje)
        cp = gerar_numero_titulo_financeiro(TituloFinanceiro.Tipo.PAGAR, self.hoje)
        self.assertTrue(cr.startswith('CR-'))
        self.assertTrue(cp.startswith('CP-'))

    def test_nao_permite_numero_duplicado(self):
        t1 = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=self.hoje,
            data_vencimento=self.hoje,
            valor_original=Decimal('10.00'),
            usuario=self.user,
        )
        t2 = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=self.hoje,
            data_vencimento=self.hoje,
            valor_original=Decimal('20.00'),
            usuario=self.user,
        )
        self.assertNotEqual(t1.numero, t2.numero)

    def test_titulo_manual_exige_vencimento(self):
        with self.assertRaises(ValueError):
            criar_titulo_financeiro(
                tipo=TituloFinanceiro.Tipo.RECEBER,
                cliente_id=self.cliente.pk,
                data_emissao=self.hoje,
                data_vencimento=None,
                valor_original=Decimal('10.00'),
                usuario=self.user,
            )


class FinanceiroVencimentoRelatorio40148Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ven40148', 'ven40148@test.com', 'x')
        self.cliente = Cliente.objects.create(razao_social='Cli Ven', cnpj='39053344710')
        self.hoje = timezone.localdate()
        self.venc = self.hoje + timedelta(days=12)

    def test_relatorio_exibe_vencimento_parcela(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=self.hoje,
            data_vencimento=self.venc,
            valor_original=Decimal('100.00'),
            usuario=self.user,
        )
        ven = vencimento_exibicao_titulo(titulo, hoje=self.hoje)
        self.assertEqual(ven['vencimento'], self.venc.isoformat())
        self.assertIsNone(ven['vencimento_ausente'])

        rel = relatorio_contas_receber({})
        linha = next(ln for ln in rel['linhas'] if ln['id'] == titulo.pk)
        self.assertEqual(linha['vencimento_exibicao'], self.venc.isoformat())
        self.assertEqual(linha['documento'], titulo.numero)

    def test_pdf_gerado_com_vencimento_valido_no_relatorio(self):
        criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=self.hoje,
            data_vencimento=self.venc,
            valor_original=Decimal('50.00'),
            usuario=self.user,
        )
        pdf = pdf_relatorio_contas_receber({}, user=self.user)
        self.assertTrue(pdf.startswith(b'%PDF'))
        rel = relatorio_contas_receber({})
        linha = rel['linhas'][0]
        self.assertIsNotNone(linha.get('vencimento_exibicao'))
        self.assertFalse(linha.get('vencimento_ausente'))

    def test_parcela_herda_vencimento_titulo(self):
        titulo = criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cliente.pk,
            data_emissao=self.hoje,
            data_vencimento=self.venc,
            valor_original=Decimal('80.00'),
            usuario=self.user,
        )
        p = ParcelaFinanceira.objects.get(titulo=titulo, numero_parcela=1)
        self.assertEqual(p.data_vencimento, self.venc)


class FinanceiroPdfApi40148Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pdf40148', 'pdf40148@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cli = Cliente.objects.create(razao_social='Cli PDF', cnpj='39053344711')
        self.hoje = timezone.localdate()

    def test_pdf_contas_receber_vencimento(self):
        criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cli.pk,
            data_emissao=self.hoje,
            data_vencimento=self.hoje + timedelta(days=3),
            valor_original=Decimal('99.00'),
            usuario=self.user,
        )
        res = self.client.get('/api/financeiro/relatorios/contas-receber/pdf/', HTTP_ACCEPT='*/*')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'%PDF', res.content[:8])
