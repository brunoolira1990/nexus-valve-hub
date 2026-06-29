"""Testes — exportação de XMLs (módulo Contador)."""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.fiscal.models import NFeEntrada, NFeSaida
from nexus_erp.contador_exportacao_service import montar_zip_xmls, validar_parametros_exportacao


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class ContadorExportacaoXmlsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('contador', 'cont@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.hoje = timezone.localdate()
        self.forn = Fornecedor.objects.create(razao_social='Forn XML', cnpj=_cnpj(), uf='SC')

    def test_validacao_periodo(self):
        with self.assertRaises(Exception):
            validar_parametros_exportacao(inicio='2026-06-10', fim='2026-06-01', tipo='todos')

    def test_exporta_zip_nfe_entrada(self):
        chave = '1' * 44
        NFeEntrada.objects.create(
            numero='100',
            serie='1',
            chave_acesso=chave,
            fornecedor=self.forn,
            data=self.hoje,
            valor_total=Decimal('50'),
            xml_importado='<?xml version="1.0"?><nfe>teste</nfe>',
        )
        conteudo, nome = montar_zip_xmls(inicio=self.hoje, fim=self.hoje, tipo='nfe_entrada')
        self.assertIn('nfe_entrada', nome)
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            self.assertEqual(len(zf.namelist()), 1)
            self.assertIn(chave, zf.namelist()[0])

    def test_exporta_zip_nfe_saida(self):
        chave = '3' * 44
        cliente = Cliente.objects.create(razao_social='Cli XML', cnpj=_cnpj(), uf='SC')
        NFeSaida.objects.create(
            numero='200',
            cliente=cliente,
            chave_acesso=chave,
            data=self.hoje,
            valor_total=Decimal('100'),
            xml_autorizado='<?xml version="1.0"?><nfeProc><NFe>autorizado</NFe></nfeProc>',
        )
        conteudo, nome = montar_zip_xmls(inicio=self.hoje, fim=self.hoje, tipo='nfe_saida')
        self.assertIn('nfe_saida', nome)
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            self.assertEqual(len(zf.namelist()), 1)
            self.assertIn(chave, zf.namelist()[0])

    def test_api_exportar_xmls(self):
        NFeEntrada.objects.create(
            numero='101',
            serie='1',
            chave_acesso='2' * 44,
            fornecedor=self.forn,
            data=self.hoje,
            valor_total=Decimal('10'),
            xml_importado='<nfe>api</nfe>',
        )
        resp = self.client.get(
            '/api/contador/exportar-xmls/',
            {'inicio': self.hoje.isoformat(), 'fim': self.hoje.isoformat(), 'tipo': 'nfe_entrada'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            self.assertGreaterEqual(len(zf.namelist()), 1)

    def test_api_sem_xml_retorna_400(self):
        resp = self.client.get(
            '/api/contador/exportar-xmls/',
            {'inicio': date(2020, 1, 1).isoformat(), 'fim': date(2020, 1, 31).isoformat(), 'tipo': 'cte'},
        )
        self.assertEqual(resp.status_code, 400)
