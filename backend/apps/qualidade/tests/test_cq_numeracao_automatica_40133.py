"""ERP 4.0.15.2.33 — numeração automática CQ-AAAAMMDD-NNNN."""

from __future__ import annotations

import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.qualidade.models import CertificadoQualidade, SequenciaCertificadoQualidade
from apps.qualidade.serializers import CertificadoQualidadeSerializer
from apps.qualidade.services.numeracao_certificado_qualidade import (
    extrair_sequencial_cq_automatico,
    gerar_numero_certificado_qualidade,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _grant_cq(user):
    ct = ContentType.objects.get_for_model(CertificadoQualidade)
    for codename in ('add_certificadoqualidade', 'change_certificadoqualidade', 'view_certificadoqualidade'):
        user.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
    return get_user_model().objects.get(pk=user.pk)


class CQNumeracaoServicoTests(TestCase):
    def setUp(self):
        self.hoje = date(2026, 6, 24)
        self._re = r'^CQ-20260624-\d{4}$'

    def test_gerar_formato_e_sequencia(self):
        n1 = gerar_numero_certificado_qualidade(self.hoje)
        n2 = gerar_numero_certificado_qualidade(self.hoje)
        self.assertRegex(n1, self._re)
        self.assertRegex(n2, self._re)
        self.assertNotEqual(n1, n2)
        par1 = extrair_sequencial_cq_automatico(n1)
        par2 = extrair_sequencial_cq_automatico(n2)
        self.assertEqual(par1[0], self.hoje)
        self.assertEqual(par2[0], self.hoje)
        self.assertEqual(par2[1], par1[1] + 1)

    def test_sequencia_reinicia_em_outro_dia(self):
        n_hoje = gerar_numero_certificado_qualidade(self.hoje)
        n_ontem = gerar_numero_certificado_qualidade(date(2026, 6, 23))
        self.assertRegex(n_ontem, r'^CQ-20260623-0001$')
        self.assertNotEqual(n_hoje, n_ontem)


class CQNumeracaoSerializerTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(razao_social='Cli CQ Num', cnpj=_cnpj())
        self.hoje = date.today()

    def _payload_rascunho(self, **extra):
        base = {
            'status': CertificadoQualidade.Status.RASCUNHO,
            'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            'numero': '',
            'serie': '',
            'nota_fiscal_numero': '100',
            'cliente_nome_snapshot': self.cliente.razao_social,
            'itens': [],
        }
        base.update(extra)
        return base

    def test_criar_sem_numero_gera_automatico(self):
        ser = CertificadoQualidadeSerializer(data=self._payload_rascunho())
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertRegex(obj.numero, rf'^CQ-{self.hoje.strftime("%Y%m%d")}-\d{{4}}$')
        self.assertEqual(obj.numero_formatado, obj.numero)

    def test_edicao_preserva_numero(self):
        cert = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQ300',
            nota_fiscal_numero='1',
            cliente=self.cliente,
        )
        ser = CertificadoQualidadeSerializer(
            cert,
            data={'numero': 'CQ-99999999-9999', 'nota_fiscal_numero': '2', 'itens': []},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.numero, 'CQ300')

    def test_legado_manual_preservado(self):
        cert = CertificadoQualidade.objects.create(
            status=CertificadoQualidade.Status.EMITIDO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
            numero='CQLEGADO',
            nota_fiscal_numero='1',
            cliente=self.cliente,
            data_emissao=self.hoje,
        )
        data = CertificadoQualidadeSerializer(cert).data
        self.assertEqual(data['numero'], 'CQLEGADO')
        self.assertEqual(data['numero_formatado'], 'CQLEGADO')


class CQNumeracaoAPITests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:6]
        self.cliente = Cliente.objects.create(razao_social='Cli API Num', cnpj=_cnpj())
        u = get_user_model().objects.create_user(f'cq_num_{s}', 'cqnum@test.com', 'x')
        self.user = _grant_cq(u)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('certificado-qualidade-list')
        self.hoje = date.today()

    def test_api_criar_sem_numero(self):
        r = self.client.post(
            self.url,
            {
                'status': 'rascunho',
                'tipo_certificado': 'PADRAO_POR_NFE',
                'numero': '',
                'serie': '',
                'nota_fiscal_numero': '88',
                'cliente_nome_snapshot': self.cliente.razao_social,
                'itens': [],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertRegex(body['numero'], rf'^CQ-{self.hoje.strftime("%Y%m%d")}-\d{{4}}$')


class CQNumeracaoConcorrenciaTests(TestCase):
    def test_multiplas_alocacoes_sequenciais_sem_duplicar(self):
        hoje = date(2026, 6, 24)
        numeros = [gerar_numero_certificado_qualidade(hoje) for _ in range(5)]
        self.assertEqual(len(set(numeros)), 5)
        seq = SequenciaCertificadoQualidade.objects.get(data_referencia=hoje)
        self.assertEqual(seq.proximo_numero, 6)
