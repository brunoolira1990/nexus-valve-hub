"""Elegibilidade de NF-e Saída para Certificado de Qualidade."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import count

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.fiscal.models import NFeSaida
from apps.qualidade.models import CertificadoQualidade
from apps.qualidade.nfe_elegivel_cq import (
    MSG_NFE_INELEGIVEL_CQ,
    buscar_nfes_elegiveis_cq,
    nfe_elegivel_para_certificado_qualidade,
)

_cnpj_seq = count(1)


def _cliente(**kwargs):
    n = next(_cnpj_seq)
    defaults = {
        'razao_social': f'Cliente CQ Elegivel {n}',
        'cnpj': f'{n:08d}0001{n % 90:02d}',
    }
    defaults.update(kwargs)
    return Cliente.objects.create(**defaults)


def _nf(**kwargs) -> NFeSaida:
    defaults = {
        'numero': 'RASCUNHO-FAT-99',
        'cliente': _cliente(),
        'data': date(2026, 7, 14),
        'valor_total': Decimal('100.00'),
        'status': 'RASCUNHO',
        'status_emissao_sefaz': '',
        'numero_nfe': '',
        'serie_nfe': '',
        'protocolo_autorizacao': '',
        'cstat_autorizacao': '',
        'xml_autorizado': '',
    }
    defaults.update(kwargs)
    if 'cliente' not in kwargs:
        defaults['cliente'] = _cliente()
    return NFeSaida.objects.create(**defaults)


def _nf_autorizada_producao(**kwargs) -> NFeSaida:
    base = {
        'numero': 'RASCUNHO-FAT-28',
        'status': 'AUTORIZADA_PRODUCAO',
        'status_emissao_sefaz': NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        'numero_nfe': '12345',
        'serie_nfe': '1',
        'protocolo_autorizacao': '135260000000001',
        'cstat_autorizacao': '100',
        'xml_autorizado': '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>',
        'ambiente_emissao': 'producao',
    }
    base.update(kwargs)
    return _nf(**base)


class NfeElegivelCqUnitTests(TestCase):
    def test_autorizada_producao_elegivel(self):
        nf = _nf_autorizada_producao()
        self.assertTrue(nfe_elegivel_para_certificado_qualidade(nf))

    def test_autorizada_homologacao_elegivel(self):
        nf = _nf_autorizada_producao(
            status='AUTORIZADA_HOMOLOGACAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            ambiente_emissao='homologacao',
            numero_nfe='99',
            serie_nfe='0',
        )
        self.assertTrue(nfe_elegivel_para_certificado_qualidade(nf))

    def test_rascunho_nao_elegivel(self):
        nf = _nf(numero='RASCUNHO-FAT-28')
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_sem_numero_fiscal_nao_elegivel(self):
        nf = _nf_autorizada_producao(numero_nfe='', serie_nfe='1')
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_cancelada_nao_elegivel(self):
        nf = _nf_autorizada_producao(status='CANCELADA_PRODUCAO')
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_descartada_nao_elegivel(self):
        nf = _nf(status='DESCARTADA_INTERNA', numero='RASCUNHO-FAT-1')
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_autorizada_interna_sem_sefaz_nao_elegivel(self):
        nf = _nf(
            status='AUTORIZADA_INTERNA',
            numero_nfe='10',
            serie_nfe='1',
            protocolo_autorizacao='x',
            cstat_autorizacao='100',
            xml_autorizado='<nfeProc/>',
        )
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_sem_protocolo_nao_elegivel(self):
        nf = _nf_autorizada_producao(protocolo_autorizacao='')
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_busca_por_numero_fiscal(self):
        _nf_autorizada_producao(numero_nfe='12345')
        _nf(numero='RASCUNHO-FAT-28')
        res = buscar_nfes_elegiveis_cq(search='12345', limit=20)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['numero_nfe'], '12345')
        self.assertIn('NF-e nº', res[0]['label_principal'])
        self.assertNotIn('RASCUNHO-FAT', res[0]['label_principal'])
        self.assertNotIn('xml_autorizado', res[0])

    def test_busca_cliente_so_elegiveis(self):
        cli = _cliente(razao_social='Acme Valvulas SA')
        _nf_autorizada_producao(cliente=cli, numero_nfe='777')
        _nf(cliente=cli, numero='RASCUNHO-FAT-7')
        res = buscar_nfes_elegiveis_cq(search='Acme', limit=20)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['numero_nfe'], '777')


class NfeElegivelCqApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('cq_nfe', 'cq_nfe@test.com', 'x')
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        self.cli = _cliente()

    def test_endpoint_lista_somente_elegiveis(self):
        ok = _nf_autorizada_producao(cliente=self.cli, numero_nfe='555')
        _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        res = self.client_api.get('/api/certificados-qualidade/nfes-elegiveis/', {'search': '555', 'limit': 20})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in res.data]
        self.assertEqual(ids, [ok.pk])
        self.assertTrue(res.data[0]['label_principal'].startswith('NF-e nº'))
        self.assertNotIn('RASCUNHO-FAT', res.data[0]['label_principal'])

    def test_preencher_bloqueia_rascunho(self):
        nf = _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        res = self.client_api.post(
            '/api/certificados-qualidade/preencher-por-nfe/',
            {'nf_saida_id': nf.pk},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['detail'], MSG_NFE_INELEGIVEL_CQ)

    def test_salvar_bloqueia_rascunho(self):
        nf = _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        res = self.client_api.post(
            '/api/certificados-qualidade/',
            {
                'status': CertificadoQualidade.Status.RASCUNHO,
                'tipo_certificado': CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
                'numero': '',
                'serie': '',
                'cliente': self.cli.id,
                'cliente_nome_snapshot': self.cli.razao_social,
                'nota_fiscal': nf.pk,
                'itens': [],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nota_fiscal', res.data)

    def test_preencher_autorizada_ok(self):
        nf = _nf_autorizada_producao(cliente=self.cli, numero_nfe='8888', serie_nfe='1')
        res = self.client_api.post(
            '/api/certificados-qualidade/preencher-por-nfe/',
            {'nf_saida_id': nf.pk},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['nota_fiscal'], nf.pk)
        self.assertNotIn('RASCUNHO-FAT', res.data['nota_fiscal_numero'])
        self.assertIn('8888', res.data['nota_fiscal_numero'])
