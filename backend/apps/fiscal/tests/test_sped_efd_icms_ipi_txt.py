"""F3 — smoke test geração TXT EFD ICMS/IPI prévia + reforma no fechamento."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.apuracao_fiscal.models import ApuracaoFiscal, ApuracaoReforma
from apps.apuracao_fiscal.services.fechamento import criar_rascunho, fechar_periodo
from apps.cadastros.models import Empresa
from apps.fiscal.services.sped_efd_icms_ipi_txt import gerar_sped_efd_icms_ipi_txt

User = get_user_model()


class SpedEfdIcmsIpiTxtTest(TestCase):
    def setUp(self) -> None:
        self.emp = Empresa.objects.create(
            razao_social='Nexus F3 SPED',
            cnpj='66.666.666/0001-66',
            ie='123456',
            uf='SP',
            regime_tributario='Lucro Real',
        )
        self.user = User.objects.create_user('f3sped', 'f3@test.com', 'x')
        self.ap = criar_rascunho(
            {
                'empresa_id': self.emp.id,
                'data_inicio': '2026-07-01',
                'data_fim': '2026-07-31',
                'fonte': 'HISTORICOS',
            },
            usuario=self.user,
        )
        ApuracaoFiscal.objects.filter(pk=self.ap.pk).update(
            saldo_icms=Decimal('10.00'),
            icms_debito=Decimal('50.00'),
            icms_credito=Decimal('40.00'),
            valor_saidas=Decimal('1000.00'),
            valor_entradas=Decimal('800.00'),
        )
        self.ap.refresh_from_db()

    def test_txt_exige_fechado(self) -> None:
        from apps.apuracao_fiscal.services.fechamento import ApuracaoFiscalError

        with self.assertRaises(ApuracaoFiscalError) as ctx:
            gerar_sped_efd_icms_ipi_txt(self.ap)
        self.assertEqual(ctx.exception.codigo, 'APURACAO_NAO_FECHADA_SPED')

    def test_smoke_estrutura_txt(self) -> None:
        fechada = fechar_periodo(self.ap.id, usuario=self.user)
        txt = gerar_sped_efd_icms_ipi_txt(fechada)
        self.assertIn('PREVIA ESTRUTURAL', txt)
        self.assertIn('|0000|', txt)
        self.assertIn('|C100|', txt)
        self.assertIn('|C170|', txt)
        self.assertIn('|C190|', txt)
        self.assertIn('|E110|', txt)
        self.assertIn('|9999|', txt)
        # reforma persistida
        self.assertTrue(ApuracaoReforma.objects.filter(apuracao=fechada).exists())
        ref = fechada.reforma
        self.assertIn('por_documento', ref.detalhe_json)

    def test_api_download(self) -> None:
        fechar_periodo(self.ap.id, usuario=self.user)
        client = APIClient()
        client.force_authenticate(user=self.user)
        r = client.get(f'/api/fiscal/apuracoes/{self.ap.id}/sped-efd-icms-ipi/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('text/plain', r['Content-Type'])
        body = r.content.decode('utf-8')
        self.assertIn('|0000|', body)
        self.assertIn('attachment', r['Content-Disposition'])
