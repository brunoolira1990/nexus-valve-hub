"""Dashboard BI — fase 1: fiscal produção, Central DF-e e permissão financeiro."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.fiscal.models import NFeDestinadaManifestacao, NFeSaida


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class DashboardBIFase1Tests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('bi_fase1_admin', 'admin@test.com', 'x')
        self.financeiro_user = get_user_model().objects.create_user('bi_fin', 'fin@test.com', 'x')
        ct = ContentType.objects.get(app_label='financeiro', model='titulofinanceiro')
        perm = Permission.objects.get(content_type=ct, codename='view_titulofinanceiro')
        self.financeiro_user.user_permissions.add(perm)

        self.client = APIClient()
        self.cliente = Cliente.objects.create(razao_social='Cliente BI F1', cnpj=_cnpj(), uf='SC')
        self.empresa = Empresa.objects.create(razao_social='Empresa BI F1', cnpj=_cnpj(), uf='SP')
        self.hoje = timezone.localdate()

    def test_fiscal_inclui_kpis_producao(self):
        NFeSaida.objects.create(
            numero='NF-PROD',
            cliente=self.cliente,
            empresa_emitente=self.empresa,
            data=self.hoje,
            status='AUTORIZADA_PRODUCAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
            valor_total=Decimal('100.00'),
        )
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/fiscal/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['nfe_auth_prod']['valor'], 1)
        self.assertEqual(data['hero_kpi_id'], 'nfe_auth_prod')

    def test_fiscal_inclui_kpis_central_dfe(self):
        NFeDestinadaManifestacao.objects.create(
            empresa=self.empresa,
            chave_acesso='35260622222222222222550010000009998887766554',
            cnpj_destinatario=''.join(c for c in self.empresa.cnpj if c.isdigit()),
            cnpj_emitente='22222222000122',
            razao_social_emitente='Fornecedor BI',
            dh_emissao=timezone.make_aware(datetime(2026, 6, 10, 10, 0, 0)),
            valor_nf=Decimal('500.00'),
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            status_manifestacao=NFeDestinadaManifestacao.StatusManifestacao.PENDENTE,
            status_xml=NFeDestinadaManifestacao.StatusXml.RESUMO,
        )
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/fiscal/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['dfe_aguardando_manifestacao']['valor'], 1)
        links = {lnk['id'] for lnk in data.get('links', [])}
        self.assertIn('central_dfe', links)
        alertas = [a['titulo'] for a in data.get('alertas', [])]
        self.assertIn('Manifestação pendente', alertas)

    def test_usuario_financeiro_pode_ver_dashboard_financeiro(self):
        self.client.force_authenticate(self.financeiro_user)
        perms = self.client.get('/api/dashboard/permissoes/').json()
        self.assertTrue(perms['pode_ver_financeiro'])
        resp = self.client.get('/api/dashboard/financeiro/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('saldo_previsto', {k['id'] for k in resp.json()['kpis']})

    def test_home_fiscal_expoe_hero_kpi_id(self):
        NFeSaida.objects.create(
            numero='NF-HOM',
            cliente=self.cliente,
            data=self.hoje,
            status='RASCUNHO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
            valor_total=1,
        )
        self.client.force_authenticate(self.admin)
        data = self.client.get('/api/dashboard/home/').json()
        fiscal = next(m for m in data['modulos'] if m['modulo'] == 'fiscal')
        self.assertEqual(fiscal['hero_kpi_id'], 'nfe_rej_homolog')
