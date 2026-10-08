"""F2 — ajustes fiscais manuais: cálculo, trava RASCUNHO e APIs."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.apuracao_fiscal.models import ApuracaoFiscal, LogsAuditoriaApuracao
from apps.apuracao_fiscal.services.ajustes import (
    adicionar_ajuste,
    impacto_ajuste,
    remover_ajuste,
)
from apps.apuracao_fiscal.services.fechamento import ApuracaoFiscalError, criar_rascunho, fechar_periodo
from apps.cadastros.models import Empresa

User = get_user_model()


class ImpactoAjusteCalculoTest(SimpleTestCase):
    def test_sinais(self) -> None:
        self.assertEqual(impacto_ajuste('DEBITO', '10.00'), Decimal('10.00'))
        self.assertEqual(impacto_ajuste('CREDITO', '10.00'), Decimal('-10.00'))
        self.assertEqual(impacto_ajuste('ESTORNO', '5.50'), Decimal('-5.50'))


class AjustesManuaisServiceTest(TestCase):
    def setUp(self) -> None:
        self.emp = Empresa.objects.create(
            razao_social='Nexus F2',
            cnpj='44.444.444/0001-44',
            ie='1',
            regime_tributario='Lucro Real',
        )
        self.user = User.objects.create_user('f2user', 'f2@test.com', 'x')
        self.dados = {
            'empresa_id': self.emp.id,
            'data_inicio': '2026-05-01',
            'data_fim': '2026-05-31',
            'tipo': 'AMBOS',
            'fonte': 'HISTORICOS',
        }
        self.ap = criar_rascunho(self.dados, usuario=self.user)
        # força snapshot conhecido para teste de saldo
        ApuracaoFiscal.objects.filter(pk=self.ap.pk).update(saldo_icms=Decimal('100.00'))
        self.ap.refresh_from_db()

    def test_adicionar_e_saldo_final(self) -> None:
        a1, liq, final = adicionar_ajuste(
            self.ap.id,
            tipo='DEBITO',
            valor='20.00',
            motivo='Ajuste débito ICMS extra',
            usuario=self.user,
        )
        self.assertEqual(a1.tipo, 'DEBITO')
        self.assertEqual(liq, Decimal('20.00'))
        self.assertEqual(final, Decimal('120.00'))
        self.assertTrue(
            LogsAuditoriaApuracao.objects.filter(
                apuracao=self.ap, acao=LogsAuditoriaApuracao.Acao.AJUSTE_ADICIONADO
            ).exists()
        )

        a2, liq2, final2 = adicionar_ajuste(
            self.ap.id,
            tipo='CREDITO',
            valor='15.00',
            motivo='Crédito complementar do período',
            usuario=self.user,
        )
        self.assertEqual(a2.tipo, 'CREDITO')
        self.assertEqual(liq2, Decimal('5.00'))
        self.assertEqual(final2, Decimal('105.00'))

        _, liq3, final3 = remover_ajuste(self.ap.id, a1.id, usuario=self.user)
        self.assertEqual(liq3, Decimal('-15.00'))
        self.assertEqual(final3, Decimal('85.00'))
        self.assertTrue(
            LogsAuditoriaApuracao.objects.filter(
                apuracao=self.ap, acao=LogsAuditoriaApuracao.Acao.AJUSTE_REMOVIDO
            ).exists()
        )

    def test_bloqueia_ajuste_quando_fechado(self) -> None:
        fechar_periodo(self.ap.id, usuario=self.user)
        with self.assertRaises(ApuracaoFiscalError) as ctx:
            adicionar_ajuste(
                self.ap.id,
                tipo='DEBITO',
                valor='1.00',
                motivo='não deveria passar',
                usuario=self.user,
            )
        self.assertEqual(ctx.exception.codigo, 'APURACAO_FECHADA_AJUSTE')


class AjustesManuaisApiTest(TestCase):
    def setUp(self) -> None:
        self.emp = Empresa.objects.create(
            razao_social='Nexus F2 API',
            cnpj='55.555.555/0001-55',
            ie='2',
        )
        self.user = User.objects.create_user('f2api', 'f2api@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.ap = criar_rascunho(
            {
                'empresa_id': self.emp.id,
                'data_inicio': '2026-06-01',
                'data_fim': '2026-06-30',
            },
            usuario=self.user,
        )
        ApuracaoFiscal.objects.filter(pk=self.ap.pk).update(saldo_icms=Decimal('50.00'))

    def test_post_get_delete(self) -> None:
        url = f'/api/fiscal/apuracoes/{self.ap.id}/ajustes/'
        r = self.client.post(
            url,
            {'tipo': 'DEBITO', 'valor': '10.00', 'motivo': 'Débito de conferência'},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['saldo_final'], 60.0)
        ajuste_id = r.data['ajuste']['id']

        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['quantidade'], 1)
        self.assertEqual(r2.data['saldo_final'], 60.0)

        r3 = self.client.delete(f'/api/fiscal/apuracoes/{self.ap.id}/ajustes/{ajuste_id}/')
        self.assertEqual(r3.status_code, 200, r3.content)
        self.assertEqual(r3.data['saldo_final'], 50.0)

    def test_post_fechado_retorna_403(self) -> None:
        fechar_periodo(self.ap.id, usuario=self.user)
        r = self.client.post(
            f'/api/fiscal/apuracoes/{self.ap.id}/ajustes/',
            {'tipo': 'CREDITO', 'valor': '1.00', 'motivo': 'tentativa indevida'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data['codigo'], 'APURACAO_FECHADA_AJUSTE')

    def test_motivo_curto_400(self) -> None:
        r = self.client.post(
            f'/api/fiscal/apuracoes/{self.ap.id}/ajustes/',
            {'tipo': 'DEBITO', 'valor': '1.00', 'motivo': 'abc'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
