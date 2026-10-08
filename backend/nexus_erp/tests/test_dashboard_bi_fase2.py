"""Dashboard BI — fase 2: pendências de qualidade e estoque operacional."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.corridas.models import Corrida
from apps.produtos.models import Produto
from apps.qualidade.models import CertificadoFornecedorEntrada, CertificadoQualidade, ItemCertificadoQualidade


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class DashboardBIFase2Tests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('bi_fase2', 'admin@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.hoje = timezone.localdate()
        self.produto = Produto.objects.create(codigo_completo='BI-F2', descricao='Produto BI', material='Aço')
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn BI', cnpj=_cnpj(), uf='SC')

    def test_qualidade_pendencias_rastreabilidade(self):
        cq = CertificadoQualidade.objects.create(numero='CQ-F2', status='rascunho')
        ItemCertificadoQualidade.objects.create(
            certificado=cq,
            ordem=1,
            descricao_material='Item sem corrida',
            incluir_no_certificado=True,
        )
        CertificadoFornecedorEntrada.objects.create(
            numero_certificado_fornecedor='CF-F2',
            status=CertificadoFornecedorEntrada.Status.RASCUNHO,
        )
        data = self.client.get('/api/dashboard/qualidade/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['cq_rascunho']['valor'], 1)
        self.assertGreaterEqual(k['cq_rastreabilidade_pendente']['valor'], 1)
        self.assertGreaterEqual(k['cf_rascunho']['valor'], 1)
        alertas = [a['titulo'] for a in data.get('alertas', [])]
        self.assertIn('Rastreabilidade pendente', alertas)

    def test_estoque_produto_sem_corrida_cadastrada(self):
        data = self.client.get('/api/dashboard/estoque/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertGreaterEqual(k['produtos_sem_corrida']['valor'], 1)

    def test_estoque_produto_com_corrida_reduz_pendencia(self):
        Corrida.objects.create(
            numero='CORR-BI-F2',
            produto=self.produto,
            fornecedor=self.fornecedor,
            data_recebimento=self.hoje,
        )
        data = self.client.get('/api/dashboard/estoque/').json()
        k = {x['id']: x for x in data['kpis']}
        self.assertEqual(k['produtos_sem_corrida']['valor'], 0)

    def test_home_expoe_hero_qualidade(self):
        cq = CertificadoQualidade.objects.create(numero='CQ-HOME', status='rascunho')
        ItemCertificadoQualidade.objects.create(
            certificado=cq,
            ordem=1,
            descricao_material='Pendente',
            incluir_no_certificado=True,
        )
        data = self.client.get('/api/dashboard/home/').json()
        qualidade = next(m for m in data['modulos'] if m['modulo'] == 'qualidade')
        self.assertEqual(qualidade['hero_kpi_id'], 'cq_rastreabilidade_pendente')
