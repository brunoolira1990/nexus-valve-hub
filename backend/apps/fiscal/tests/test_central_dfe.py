"""ERP 4.0.14.x — DF-e recebidos contra CNPJ da empresa."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa, Fornecedor
from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeDestinadaManifestacao,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)


def _dh() -> datetime:
    return timezone.make_aware(datetime(2026, 5, 10, 12, 0, 0))


class CentralDfeRecebidosApiTest(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='central_dfe', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('central-dfe-list')
        self.dh = _dh()
        self.emp = Empresa.objects.create(razao_social='Nexus Teste', cnpj='11.111.111/0001-11')
        self.forn = Fornecedor.objects.create(razao_social='Forn Central', cnpj='22.222.222/0001-22')

        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='1' * 44,
            numero='100',
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('150'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='2' * 44,
            numero='200',
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb='2',
            cstat='100',
            valor_total_nf=Decimal('80'),
            fornecedor_emitente=self.forn,
            empresa_destinataria=self.emp,
        )
        CTeHistoricoImportado.objects.create(
            chave_acesso='4' * 44,
            numero='400',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_servico=Decimal('90'),
            empresa_tomadora=self.emp,
            status_conferencia='IMPORTADO',
        )
        NFeSaidaHistoricaImportada.objects.create(
            chave_acesso='3' * 44,
            numero='300',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('220'),
            empresa_emitente=self.emp,
            cancelada=False,
        )

    def test_visao_padrao_somente_pendentes(self) -> None:
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)
        for row in resp.data['results']:
            self.assertIn(row['status_entrada'], {'PENDENTE_ENTRADA', 'IMPORTADO_BASE'})

    def test_listagem_com_tratados(self) -> None:
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk, 'incluir_tratados': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)
        tipos = {r['tipo_documento'] for r in resp.data['results']}
        self.assertEqual(tipos, {'NFE_ENTRADA', 'CTE'})
        self.assertNotIn('xml', resp.data['results'][0])

    def test_exclui_homologacao(self) -> None:
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk, 'incluir_tratados': 'true'})
        chaves = [r['chave_acesso'] for r in resp.data['results']]
        self.assertNotIn('2' * 44, chaves)

    def test_nao_lista_nfe_saida_historica(self) -> None:
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk, 'incluir_tratados': 'true'})
        for row in resp.data['results']:
            self.assertNotEqual(row['tipo_documento'], 'NFE_SAIDA')

    def test_filtro_tipo_nfe_entrada(self) -> None:
        resp = self.client.get(
            self.url,
            {'empresa_id': self.emp.pk, 'tipo_documento': 'NFE_ENTRADA', 'incluir_tratados': 'true'},
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['tipo_documento'], 'NFE_ENTRADA')

    def test_ja_lancado_oculto_na_visao_padrao(self) -> None:
        NFeEntrada.objects.create(
            numero='500',
            serie='1',
            chave_acesso='1' * 44,
            fornecedor=self.forn,
            data=self.dh.date(),
            valor_total=Decimal('60'),
        )
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk})
        chaves = [r['chave_acesso'] for r in resp.data['results']]
        self.assertNotIn('1' * 44, chaves)

    def test_status_ja_lancado_com_incluir_tratados(self) -> None:
        NFeEntrada.objects.create(
            numero='501',
            serie='1',
            chave_acesso='1' * 44,
            fornecedor=self.forn,
            data=self.dh.date(),
            valor_total=Decimal('60'),
        )
        resp = self.client.get(
            self.url,
            {'empresa_id': self.emp.pk, 'status_entrada': 'JA_LANCADO', 'incluir_tratados': 'true'},
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['status_entrada'], 'JA_LANCADO')

    def test_lista_resumo_destinado_sem_xml_historico(self) -> None:
        from django.utils import timezone

        chave_resumo = '5' * 44
        NFeDestinadaManifestacao.objects.create(
            empresa=self.emp,
            chave_acesso=chave_resumo,
            nsu='123456789012345',
            cnpj_destinatario='11111111000111',
            cnpj_emitente='22222222000122',
            razao_social_emitente='Forn Resumo',
            dh_emissao=timezone.make_aware(datetime(2026, 6, 20, 10, 0, 0)),
            valor_nf=Decimal('250'),
            ambiente=NFeDestinadaManifestacao.Ambiente.PRODUCAO,
            status_xml=NFeDestinadaManifestacao.StatusXml.RESUMO,
        )
        resp = self.client.get(self.url, {'empresa_id': self.emp.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        chaves = [r['chave_acesso'] for r in resp.data['results']]
        self.assertIn(chave_resumo, chaves)
        row = next(r for r in resp.data['results'] if r['chave_acesso'] == chave_resumo)
        self.assertEqual(row['xml_armazenado'], False)
        self.assertEqual(row['status_entrada'], 'IMPORTADO_BASE')
