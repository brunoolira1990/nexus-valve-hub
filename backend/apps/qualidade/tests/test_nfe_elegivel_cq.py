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

XML_ASSINADO_SEPARADO = (
    '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
    '<infNFe Id="NFe35260512345678000199550090000000021000000021" versao="4.00">'
    '<ide><tpAmb>2</tpAmb></ide></infNFe></NFe>'
)
XML_PROTOCOLO_SEPARADO = (
    '<protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>'
    '<nProt>135260000000001</nProt></infProt></protNFe>'
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


def _nf_autorizada_homologacao(**kwargs) -> NFeSaida:
    base = {
        'numero': 'RASCUNHO-FAT-28',
        'status': 'AUTORIZADA_HOMOLOGACAO',
        'status_emissao_sefaz': NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        'numero_nfe': '99',
        'serie_nfe': '0',
        'protocolo_autorizacao': '135260000000002',
        'cstat_autorizacao': '100',
        'xml_autorizado': '<?xml version="1.0"?><nfeProc><NFe/></nfeProc>',
        'ambiente_emissao': 'homologacao',
    }
    base.update(kwargs)
    return _nf(**base)


class NfeElegivelCqUnitTests(TestCase):
    def test_autorizada_producao_elegivel(self):
        nf = _nf_autorizada_producao()
        self.assertTrue(nfe_elegivel_para_certificado_qualidade(nf))

    def test_autorizada_homologacao_nao_elegivel(self):
        nf = _nf_autorizada_homologacao()
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_busca_exclui_homologacao(self):
        _nf_autorizada_homologacao(numero_nfe='4242')
        _nf_autorizada_producao(numero_nfe='4243')
        res = buscar_nfes_elegiveis_cq(search='424', limit=20)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['numero_nfe'], '4243')
        self.assertEqual(res[0]['ambiente_badge'], 'Produção')

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

    def test_sem_xml_autorizado_persistido_nao_elegivel(self):
        nf = _nf_autorizada_producao(xml_autorizado='')
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))

    def test_xml_apenas_montavel_nao_elegivel(self):
        from apps.fiscal.nfe_saida_bloqueio import (
            nf_tem_xml_autorizado_local,
            nf_tem_xml_autorizado_resolvido,
        )

        nf = _nf_autorizada_producao(
            xml_autorizado='',
            xml_assinado=XML_ASSINADO_SEPARADO,
            xml_protocolo=XML_PROTOCOLO_SEPARADO,
        )
        self.assertFalse(nf_tem_xml_autorizado_local(nf))
        self.assertTrue(nf_tem_xml_autorizado_resolvido(nf))
        self.assertFalse(nfe_elegivel_para_certificado_qualidade(nf))
        self.assertEqual(buscar_nfes_elegiveis_cq(search=str(nf.numero_nfe), limit=20), [])

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

    def test_preencher_bloqueia_homologacao(self):
        nf = _nf_autorizada_homologacao(cliente=self.cli, numero_nfe='3333')
        res = self.client_api.post(
            '/api/certificados-qualidade/preencher-por-nfe/',
            {'nf_saida_id': nf.pk},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['detail'], MSG_NFE_INELEGIVEL_CQ)

    def test_salvar_bloqueia_homologacao(self):
        nf = _nf_autorizada_homologacao(cliente=self.cli, numero_nfe='4444')
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

    def test_incluir_id_homologacao_legado_apenas_exibicao(self):
        nf = _nf_autorizada_homologacao(cliente=self.cli, numero_nfe='5555')
        res = self.client_api.get(
            '/api/certificados-qualidade/nfes-elegiveis/',
            {'incluir_id': nf.pk},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], nf.pk)
        self.assertFalse(res.data[0]['elegivel'])
        self.assertEqual(res.data[0]['ambiente_badge'], 'Homologação')

    def test_salvar_preserva_vinculo_legado_homologacao(self):
        nf = _nf_autorizada_homologacao(cliente=self.cli, numero_nfe='6666', serie_nfe='1')
        cert = CertificadoQualidade.objects.create(
            cliente=self.cli,
            cliente_nome_snapshot=self.cli.razao_social,
            nota_fiscal=nf,
            nota_fiscal_numero='6666/1',
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
        )
        res = self.client_api.patch(
            f'/api/certificados-qualidade/{cert.pk}/',
            {
                'observacoes': 'legado homolog mantido',
                'nota_fiscal': nf.pk,
                'itens': [],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        cert.refresh_from_db()
        self.assertEqual(cert.nota_fiscal_id, nf.pk)
        self.assertEqual(cert.observacoes, 'legado homolog mantido')

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

    def test_incluir_id_retorna_legado_inelegivel_para_exibicao(self):
        nf = _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        res = self.client_api.get(
            '/api/certificados-qualidade/nfes-elegiveis/',
            {'incluir_id': nf.pk},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], nf.pk)
        self.assertFalse(res.data[0]['elegivel'])

    def test_incluir_id_nao_contamina_busca_elegivel(self):
        ok = _nf_autorizada_producao(cliente=self.cli, numero_nfe='555')
        inelegivel = _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        res = self.client_api.get(
            '/api/certificados-qualidade/nfes-elegiveis/',
            {'search': '555', 'incluir_id': inelegivel.pk, 'limit': 20},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([r['id'] for r in res.data if r['elegivel']], [ok.pk])
        legado = next(r for r in res.data if r['id'] == inelegivel.pk)
        self.assertFalse(legado['elegivel'])

    def test_salvar_preserva_vinculo_legado_inelegivel(self):
        nf = _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        cert = CertificadoQualidade.objects.create(
            cliente=self.cli,
            cliente_nome_snapshot=self.cli.razao_social,
            nota_fiscal=nf,
            nota_fiscal_numero='RASCUNHO-FAT-28',
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
        )
        res = self.client_api.patch(
            f'/api/certificados-qualidade/{cert.pk}/',
            {
                'observacoes': 'mantido',
                'nota_fiscal': nf.pk,
                'itens': [],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        cert.refresh_from_db()
        self.assertEqual(cert.nota_fiscal_id, nf.pk)
        self.assertEqual(cert.observacoes, 'mantido')

    def test_atualizar_bloqueia_troca_para_inelegivel(self):
        ok = _nf_autorizada_producao(cliente=self.cli, numero_nfe='111')
        inelegivel = _nf(cliente=self.cli, numero='RASCUNHO-FAT-28')
        cert = CertificadoQualidade.objects.create(
            cliente=self.cli,
            cliente_nome_snapshot=self.cli.razao_social,
            nota_fiscal=ok,
            nota_fiscal_numero='111/1',
            status=CertificadoQualidade.Status.RASCUNHO,
            tipo_certificado=CertificadoQualidade.TipoCertificado.PADRAO_POR_NFE,
        )
        res = self.client_api.patch(
            f'/api/certificados-qualidade/{cert.pk}/',
            {'nota_fiscal': inelegivel.pk, 'itens': []},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nota_fiscal', res.data)
        cert.refresh_from_db()
        self.assertEqual(cert.nota_fiscal_id, ok.pk)
