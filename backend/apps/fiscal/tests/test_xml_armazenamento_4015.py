"""ERP 4.0.15.2.15 — Armazenamento de XML importado NF-e/CT-e."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeEntradaHistoricaImportada
from apps.fiscal.xml_armazenamento import ORIGEM_IMPORTACAO_MANUAL, persistir_xml_nfe_entrada


class XmlArmazenamentoTests(TestCase):
    def setUp(self):
        self.emp = Empresa.objects.create(razao_social='Empresa XML', cnpj='11.111.111/0001-11', uf='SP')
        self.dh = timezone.make_aware(datetime(2026, 6, 10, 10, 0, 0))

    def test_persistir_xml_nfe_entrada(self):
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='35260622222222222222550010000001234567890123',
            numero='123',
            serie='1',
            dh_emissao=self.dh,
            valor_total_nf=Decimal('100.00'),
            empresa_destinataria=self.emp,
        )
        xml = b'<?xml version="1.0"?><nfeProc><NFe/></nfeProc>'
        self.assertTrue(
            persistir_xml_nfe_entrada(nf, xml, origem=ORIGEM_IMPORTACAO_MANUAL, nome_arquivo='nota.xml'),
        )
        nf.refresh_from_db()
        self.assertIn('nfeProc', nf.xml_conteudo)
        self.assertEqual((nf.prot_json.get('_nexus') or {}).get('origem_xml'), ORIGEM_IMPORTACAO_MANUAL)

    def test_nao_sobrescreve_xml_existente(self):
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='35260622222222222222550010000001234567890124',
            numero='124',
            serie='1',
            dh_emissao=self.dh,
            valor_total_nf=Decimal('100.00'),
            empresa_destinataria=self.emp,
            xml_conteudo='<xml original/>',
        )
        self.assertFalse(
            persistir_xml_nfe_entrada(nf, b'<xml novo/>', origem=ORIGEM_IMPORTACAO_MANUAL),
        )
        nf.refresh_from_db()
        self.assertEqual(nf.xml_conteudo, '<xml original/>')
