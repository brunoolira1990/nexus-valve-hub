"""ERP 4.0.10.2.1 — regressão: classificacao_dfe nas bases saída e CT-e (listagem)."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.dfe_classificacao import CATEGORIA_BASE_DFE_IMPORTADA
from apps.fiscal.models import CTeHistoricoImportado, NFeSaidaHistoricaImportada


def _dh() -> datetime:
    return timezone.make_aware(datetime(2026, 5, 10, 12, 0, 0))


class ListagemClassificacaoDfe401021Test(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='dfe401021', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        dh = _dh()
        NFeSaidaHistoricaImportada.objects.create(
            chave_acesso='1' * 44,
            numero='1',
            serie='1',
            dh_emissao=dh,
            tp_amb='1',
            cstat='100',
            cancelada=False,
        )
        CTeHistoricoImportado.objects.create(
            chave_acesso='2' * 44,
            numero='2',
            serie='1',
            dh_emissao=dh,
            tp_amb='1',
            cstat='100',
            cancelado=False,
        )

    def test_lista_saida_historica_retorna_classificacao_dfe(self) -> None:
        url = reverse('nf-saida-hist-importada-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertIn('classificacao_dfe', row)
        self.assertEqual(row['classificacao_dfe']['categoria'], CATEGORIA_BASE_DFE_IMPORTADA)
        self.assertNotIn('xml', row)
        self.assertNotIn('xml_conteudo', row)

    def test_lista_cte_historico_retorna_classificacao_dfe(self) -> None:
        url = reverse('cte-hist-importado-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertIn('classificacao_dfe', row)
        self.assertEqual(row['classificacao_dfe']['categoria'], CATEGORIA_BASE_DFE_IMPORTADA)
