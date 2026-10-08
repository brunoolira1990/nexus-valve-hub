"""ERP 4.0.14.7 — PDF de relatórios financeiros (motor isolado do DANFE)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.relatorios_pdf import pdf_relatorio_contas_receber
from apps.financeiro.services.titulo import criar_titulo_financeiro


class FinanceiroRelatoriosPdf40147Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fin40147', 'fin40147@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cli = Cliente.objects.create(razao_social='Cli 40147', cnpj='39053344708')
        self.forn = Fornecedor.objects.create(razao_social='Forn 40147', cnpj='59443075000123')
        self.hoje = timezone.localdate()

    def _criar_receber(self):
        return criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=self.cli.pk,
            data_emissao=self.hoje,
            data_vencimento=self.hoje + timedelta(days=5),
            valor_original=Decimal('150.00'),
            origem_tipo=TituloFinanceiro.OrigemTipo.MANUAL,
            usuario=self.user,
        )

    def _assert_pdf_response(self, url: str, slug_part: str):
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content[:4] == b'%PDF')
        cd = res.get('Content-Disposition', '')
        self.assertIn(slug_part, cd.lower().replace('_', '-'))

    def test_pdf_contas_receber_content_type(self):
        self._criar_receber()
        self._assert_pdf_response(
            '/api/financeiro/relatorios/contas-receber/pdf/',
            'relatorio-contas-a-receber',
        )

    def test_pdf_aceita_accept_application_pdf(self):
        """Frontend antigo enviava Accept: application/pdf — não pode retornar 406."""
        self._criar_receber()
        res = self.client.get(
            '/api/financeiro/relatorios/contas-receber/pdf/',
            HTTP_ACCEPT='application/pdf',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_pdf_contas_pagar_content_type(self):
        self._assert_pdf_response(
            '/api/financeiro/relatorios/contas-pagar/pdf/',
            'relatorio-contas-a-pagar',
        )

    def test_pdf_fluxo_previsto_content_type(self):
        self._assert_pdf_response(
            '/api/financeiro/relatorios/fluxo-previsto/pdf/',
            'fluxo-previsto',
        )

    def test_pdf_categorias_content_type(self):
        self._assert_pdf_response(
            '/api/financeiro/relatorios/categorias/pdf/',
            'receitas-despesas-categoria',
        )

    def test_pdf_clientes_content_type(self):
        self._assert_pdf_response(
            '/api/financeiro/relatorios/clientes/pdf/',
            'relatorio-por-cliente',
        )

    def test_pdf_fornecedores_content_type(self):
        self._assert_pdf_response(
            '/api/financeiro/relatorios/fornecedores/pdf/',
            'relatorio-por-fornecedor',
        )

    def test_pdf_respeita_filtro_vencimento(self):
        self._criar_receber()
        res = self.client.get(
            '/api/financeiro/relatorios/contas-receber/pdf/?vencimento=proximos_30',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_pdf_incluir_cancelados(self):
        titulo = self._criar_receber()
        titulo.cancelado = True
        titulo.status = TituloFinanceiro.Status.CANCELADO
        titulo.valor_aberto = Decimal('0')
        titulo.save()
        res = self.client.get(
            '/api/financeiro/relatorios/contas-receber/pdf/?incluir_cancelados=1',
        )
        self.assertEqual(res.status_code, 200)
        pdf = pdf_relatorio_contas_receber({'incluir_cancelados': '1'}, user=self.user)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_pdf_nao_altera_titulo(self):
        titulo = self._criar_receber()
        saldo = titulo.valor_aberto
        self.client.get('/api/financeiro/relatorios/contas-receber/pdf/')
        titulo.refresh_from_db()
        self.assertEqual(titulo.valor_aberto, saldo)

    def test_pdf_nao_usa_danfe(self):
        import apps.financeiro.relatorios_pdf as mod

        src = open(mod.__file__, encoding='utf-8').read()
        self.assertNotIn('danfe_render', src)
        self.assertNotIn('brazilfiscalreport', src.lower())
        self.assertNotIn('BrazilFiscalReport', src)

    def test_requer_autenticacao(self):
        anon = APIClient()
        res = anon.get('/api/financeiro/relatorios/contas-receber/pdf/')
        self.assertIn(res.status_code, (401, 403))
