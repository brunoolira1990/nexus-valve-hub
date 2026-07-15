"""Content-Disposition do endpoint danfe-autorizado (visualizar vs baixar)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.fiscal.models import NFeSaida


PDF_MOCK = b'%PDF-1.4 mock'


@patch('apps.fiscal.nfe_saida_danfe_autorizado.gerar_danfe_autorizado_nfe_saida', return_value=(PDF_MOCK, {'danfe_origem': 'test'}))
@patch('apps.fiscal.nfe_saida_bloqueio.pode_visualizar_danfe_xml_autorizado', return_value=True)
class DanfeAutorizadoContentDispositionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('danfe_cd', 'danfe_cd@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(
            razao_social='Cliente DANFE CD',
            nome_fantasia='Cliente DANFE',
            cnpj='11222333000181',
        )
        self.nf = NFeSaida.objects.create(
            numero='1',
            cliente=self.cliente,
            data=date.today(),
            valor_total=Decimal('100'),
            status='AUTORIZADA_HOMOLOGACAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            xml_autorizado='<nfe/>',
            chave_acesso='1' * 44,
        )

    def test_inline_por_padrao(self, _pode, _gerar):
        res = self.client.get(f'/api/nf-saidas/{self.nf.pk}/danfe-autorizado/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('inline', res['Content-Disposition'])
        self.assertIn('DANFE_NFe_', res['Content-Disposition'])

    def test_attachment_com_download_param(self, _pode, _gerar):
        res = self.client.get(f'/api/nf-saidas/{self.nf.pk}/danfe-autorizado/?download=1')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('attachment', res['Content-Disposition'])

    def test_sem_autenticacao_bloqueada(self, _pode, _gerar):
        anon = APIClient()
        res = anon.get(f'/api/nf-saidas/{self.nf.pk}/danfe-autorizado/')
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
