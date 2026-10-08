"""F1 — rascunho / fechar / reabrir apuração persistida."""
from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.apuracao_fiscal.models import ApuracaoFiscal, LogsAuditoriaApuracao
from apps.apuracao_fiscal.services.fechamento import (
    ApuracaoFiscalError,
    criar_rascunho,
    fechar_periodo,
    periodo_fiscal_fechado,
    reabrir_periodo,
)
from apps.cadastros.models import Empresa

User = get_user_model()


class ApuracaoPersistidaF1Test(TestCase):
    def setUp(self) -> None:
        self.emp = Empresa.objects.create(
            razao_social='Nexus F1',
            cnpj='33.333.333/0001-33',
            ie='123',
            regime_tributario='Lucro Real',
        )
        self.user = User.objects.create_user('f1user', 'f1@test.com', 'x')
        self.admin = User.objects.create_user('f1admin', 'f1a@test.com', 'x', is_staff=True)
        self.di = date(2026, 4, 1)
        self.df = date(2026, 4, 30)
        self.dados = {
            'empresa_id': self.emp.id,
            'data_inicio': self.di.isoformat(),
            'data_fim': self.df.isoformat(),
            'tipo': 'AMBOS',
            'fonte': 'HISTORICOS',
        }

    def test_criar_rascunho_e_fechar(self) -> None:
        ap = criar_rascunho(self.dados, usuario=self.user)
        self.assertEqual(ap.status, ApuracaoFiscal.Status.RASCUNHO)
        self.assertTrue(
            LogsAuditoriaApuracao.objects.filter(
                apuracao=ap, acao=LogsAuditoriaApuracao.Acao.ABRIU
            ).exists()
        )
        self.assertFalse(periodo_fiscal_fechado(self.emp.id, self.di, self.df))

        fechada = fechar_periodo(ap.id, usuario=self.user)
        self.assertEqual(fechada.status, ApuracaoFiscal.Status.FECHADO)
        self.assertIsNotNone(fechada.fechado_em)
        self.assertTrue(periodo_fiscal_fechado(self.emp.id, self.di, self.df))
        self.assertTrue(
            LogsAuditoriaApuracao.objects.filter(
                apuracao=fechada, acao=LogsAuditoriaApuracao.Acao.FECHOU
            ).exists()
        )
        self.assertTrue(isinstance(fechada.payload_snapshot, dict))
        self.assertIn('cards', fechada.payload_snapshot)

        with self.assertRaises(ApuracaoFiscalError) as ctx:
            criar_rascunho(self.dados, usuario=self.user)
        self.assertEqual(ctx.exception.codigo, 'PERIODO_FECHADO')

        with self.assertRaises(ApuracaoFiscalError) as ctx2:
            fechar_periodo(fechada.id, usuario=self.user)
        self.assertEqual(ctx2.exception.codigo, 'JA_FECHADA')

    def test_reabrir_somente_admin(self) -> None:
        ap = criar_rascunho(self.dados, usuario=self.user)
        fechar_periodo(ap.id, usuario=self.user)

        with self.assertRaises(ApuracaoFiscalError) as ctx:
            reabrir_periodo(ap.id, usuario=self.user, motivo='tentativa sem permissão')
        self.assertEqual(ctx.exception.codigo, 'SEM_PERMISSAO_REABRIR')

        reaberta = reabrir_periodo(ap.id, usuario=self.admin, motivo='Correção fiscal do período')
        self.assertEqual(reaberta.status, ApuracaoFiscal.Status.RASCUNHO)
        self.assertIsNone(reaberta.fechado_em)
        self.assertFalse(periodo_fiscal_fechado(self.emp.id, self.di, self.df))
        self.assertTrue(
            LogsAuditoriaApuracao.objects.filter(
                apuracao=reaberta, acao=LogsAuditoriaApuracao.Acao.REABRIU
            ).exists()
        )

    def test_api_endpoints(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user)
        r = client.post('/api/fiscal/apuracoes/', self.dados, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        ap_id = r.data['id']
        self.assertEqual(r.data['status'], 'RASCUNHO')

        r2 = client.get(
            '/api/fiscal/apuracoes/periodo/',
            {
                'empresa_id': self.emp.id,
                'data_inicio': self.di.isoformat(),
                'data_fim': self.df.isoformat(),
            },
        )
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.data['periodo_fechado'])
        self.assertEqual(r2.data['apuracao']['id'], ap_id)

        r3 = client.post(f'/api/fiscal/apuracoes/{ap_id}/fechar/', {}, format='json')
        self.assertEqual(r3.status_code, 200, r3.content)
        self.assertEqual(r3.data['status'], 'FECHADO')

        # on-demand intacto
        r_od = client.get(
            '/api/fiscal/apuracao/',
            {
                'empresa_id': self.emp.id,
                'data_inicio': self.di.isoformat(),
                'data_fim': self.df.isoformat(),
            },
        )
        self.assertEqual(r_od.status_code, 200)
        self.assertIn('cards', r_od.data)

        r4 = client.post(
            f'/api/fiscal/apuracoes/{ap_id}/reabrir/',
            {'motivo': 'preciso corrigir'},
            format='json',
        )
        self.assertEqual(r4.status_code, 403)

        client.force_authenticate(user=self.admin)
        r5 = client.post(
            f'/api/fiscal/apuracoes/{ap_id}/reabrir/',
            {'motivo': 'Correção administrativa'},
            format='json',
        )
        self.assertEqual(r5.status_code, 200, r5.content)
        self.assertEqual(r5.data['status'], 'RASCUNHO')
