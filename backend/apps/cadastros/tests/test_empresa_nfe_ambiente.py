"""Ambiente NF-e no cadastro de empresa."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class EmpresaNfeAmbienteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('emp_nfe_amb', 'emp_nfe_amb@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.empresa = Empresa.objects.create(razao_social='Emitente Ambiente NF-e', cnpj=_cnpj(), uf='SP')

    def test_default_homologacao_no_modelo(self):
        self.assertEqual(self.empresa.nfe_ambiente, Empresa.NfeAmbiente.HOMOLOGACAO)

    def test_get_inclui_nfe_ambiente_e_flag_producao(self):
        resp = self.client.get(f'/api/empresas/{self.empresa.pk}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['nfe_ambiente'], 'homologacao')
        self.assertIn('nfe_producao_habilitada', data)
        self.assertFalse(data['nfe_producao_habilitada'])

    def test_patch_salva_producao(self):
        resp = self.client.patch(f'/api/empresas/{self.empresa.pk}/', {'nfe_ambiente': 'producao'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['nfe_ambiente'], 'producao')
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.nfe_ambiente, Empresa.NfeAmbiente.PRODUCAO)

    def test_patch_rejeita_ambiente_invalido(self):
        resp = self.client.patch(f'/api/empresas/{self.empresa.pk}/', {'nfe_ambiente': 'staging'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('nfe_ambiente', resp.json())

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_flag_producao_exposta_quando_habilitada(self):
        resp = self.client.get(f'/api/empresas/{self.empresa.pk}/')
        self.assertTrue(resp.json()['nfe_producao_habilitada'])

    def test_trocar_ambiente_nao_altera_numeracao(self):
        from apps.fiscal.models import NFeNumeracaoConfiguracao
        from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe

        ensure_numeracao_padrao_nfe(self.empresa)
        hom = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        )
        prod = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO,
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        )
        hom_antes = (hom.serie, hom.proximo_numero, hom.ultimo_numero_reservado)
        prod_antes = (prod.serie, prod.proximo_numero, prod.ultimo_numero_reservado)

        resp = self.client.patch(f'/api/empresas/{self.empresa.pk}/', {'nfe_ambiente': 'producao'}, format='json')
        self.assertEqual(resp.status_code, 200)

        hom.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual((hom.serie, hom.proximo_numero, hom.ultimo_numero_reservado), hom_antes)
        self.assertEqual((prod.serie, prod.proximo_numero, prod.ultimo_numero_reservado), prod_antes)
