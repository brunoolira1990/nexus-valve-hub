"""Filtros combinados da listagem NF-e Entrada histórica importada."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa, Fornecedor
from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada


def _dh(d: date) -> datetime:
    return timezone.make_aware(datetime(d.year, d.month, d.day, 12, 0, 0))


class NFeEntradaHistoricaListagemFiltrosTest(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='nf_hist_filtros', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse('nf-entrada-hist-importada-list')
        self.emp = Empresa.objects.create(razao_social='Empresa Filtro', cnpj='11.111.111/0001-11')
        self.forn_a = Fornecedor.objects.create(razao_social='Fornecedor Alpha', cnpj='22.222.222/0001-22')
        self.forn_b = Fornecedor.objects.create(razao_social='Fornecedor Beta', cnpj='33.333.333/0001-33')

        self.nf_sem_conf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='1' * 44,
            numero='100',
            serie='1',
            modelo='55',
            dh_emissao=_dh(date(2026, 1, 10)),
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn_a,
            empresa_destinataria=self.emp,
        )
        self.nf_pendente = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='2' * 44,
            numero='200',
            serie='1',
            modelo='55',
            dh_emissao=_dh(date(2026, 2, 15)),
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('200'),
            fornecedor_emitente=self.forn_b,
            empresa_destinataria=self.emp,
            emit_json={'xNome': 'Emitente XML Beta'},
        )
        NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf_pendente,
            status=NFeEntradaConferencia.Status.PENDENTE,
            data_entrada=date(2026, 3, 5),
        )

        self.nf_finalizada = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='3' * 44,
            numero='300',
            serie='1',
            modelo='55',
            dh_emissao=_dh(date(2026, 4, 20)),
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('300'),
            fornecedor_emitente=self.forn_a,
            empresa_destinataria=self.emp,
        )
        NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf_finalizada,
            status=NFeEntradaConferencia.Status.PREPARADA,
            data_entrada=date(2026, 4, 25),
            preparado_em=timezone.now(),
        )

        self.nf_estoque = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='4' * 44,
            numero='400',
            serie='1',
            modelo='55',
            dh_emissao=_dh(date(2026, 5, 1)),
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('400'),
            fornecedor_emitente=self.forn_b,
            empresa_destinataria=self.emp,
        )
        NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf_estoque,
            status=NFeEntradaConferencia.Status.PREPARADA,
            data_entrada=date(2026, 5, 10),
            preparado_em=timezone.now(),
            estoque_aplicado_em=timezone.now(),
        )

    def _ids(self, resp) -> set[int]:
        return {row['id'] for row in resp.data['results']}

    def test_filtro_busca_por_numero(self) -> None:
        resp = self.client.get(self.url, {'search': '200'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['numero'], '200')

    def test_filtro_busca_por_chave_parcial(self) -> None:
        resp = self.client.get(self.url, {'search': '3333'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertTrue(resp.data['results'][0]['chave_acesso'].startswith('3'))

    def test_filtro_busca_por_fornecedor_cadastro_e_xml(self) -> None:
        resp_cad = self.client.get(self.url, {'search': 'Alpha'})
        self.assertEqual(resp_cad.data['count'], 2)

        resp_xml = self.client.get(self.url, {'search': 'Emitente XML'})
        self.assertEqual(resp_xml.data['count'], 1)
        self.assertEqual(resp_xml.data['results'][0]['id'], self.nf_pendente.id)

    def test_filtro_periodo_emissao(self) -> None:
        resp = self.client.get(
            self.url,
            {'data_inicio': '2026-04-01', 'data_fim': '2026-04-30', 'tipo_data': 'emissao'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(resp), {self.nf_finalizada.id})

    def test_filtro_periodo_entrada(self) -> None:
        resp = self.client.get(
            self.url,
            {'data_inicio': '2026-03-01', 'data_fim': '2026-03-31', 'tipo_data': 'entrada'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(resp), {self.nf_pendente.id})

    def test_filtro_status_conferencia(self) -> None:
        resp_sem = self.client.get(self.url, {'status_conferencia': 'sem_conferencia'})
        self.assertEqual(resp_sem.data['count'], 1)
        self.assertEqual(resp_sem.data['results'][0]['id'], self.nf_sem_conf.id)

        resp_pend = self.client.get(self.url, {'status_conferencia': 'pendente'})
        self.assertEqual(resp_pend.data['count'], 1)
        self.assertEqual(resp_pend.data['results'][0]['id'], self.nf_pendente.id)

        resp_fin = self.client.get(self.url, {'status_conferencia': 'finalizada'})
        self.assertEqual(resp_fin.data['count'], 1)
        self.assertEqual(resp_fin.data['results'][0]['id'], self.nf_finalizada.id)

        resp_est = self.client.get(self.url, {'status_conferencia': 'estoque_aplicado'})
        self.assertEqual(resp_est.data['count'], 1)
        self.assertEqual(resp_est.data['results'][0]['id'], self.nf_estoque.id)

    def test_filtros_combinados_fornecedor_e_periodo(self) -> None:
        resp = self.client.get(
            self.url,
            {
                'fornecedor_id': self.forn_a.id,
                'data_inicio': '2026-01-01',
                'data_fim': '2026-12-31',
                'tipo_data': 'emissao',
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(resp), {self.nf_sem_conf.id, self.nf_finalizada.id})
