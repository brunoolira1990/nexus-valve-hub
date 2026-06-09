"""Fase Saída 3.1 — comparativo legado × cenário fiscal de saída."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.comercial.pricing import find_regra_fiscal_saida_com_fallback
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida
from apps.regras_fiscais.saida_fiscal import comparar_regra_fiscal_saida_legado_cenario


def _escopo_ncm(cenario, ncm: str) -> CenarioFiscalSaidaEscopo:
    return CenarioFiscalSaidaEscopo.objects.create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
    )


def _regra_saida(escopo, **kwargs) -> RegraFiscalSaida:
    defaults = {
        'ativo': True,
        'uf_origem': 'SP',
        'uf_destino': 'RJ',
        'cfop_venda': '5102',
        'tipo_operacao': 'VENDA',
        'cst_icms': '00',
        'aliquota_icms': Decimal('18'),
        'cst_ipi': '50',
        'aliquota_ipi': Decimal('5'),
        'cst_pis': '01',
        'aliquota_pis': Decimal('1.65'),
        'cst_cofins': '01',
        'aliquota_cofins': Decimal('7.6'),
    }
    defaults.update(kwargs)
    return RegraFiscalSaida.objects.create(escopo=escopo, cenario=escopo.cenario, **defaults)


class CompararSaidaFiscalTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()

    def test_iguais_quando_valores_coincidem(self):
        escopo = _escopo_ncm(self.cenario, '84818095')
        _regra_saida(escopo)
        RegraFiscal.objects.create(
            ncm='84818095',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            cst_icms='00',
            aliquota_icms=18.0,
            cst_ipi='50',
            aliquota_ipi=5.0,
            cst_pis='01',
            aliquota_pis=1.65,
            cst_cofins='01',
            aliquota_cofins=7.6,
        )
        r = comparar_regra_fiscal_saida_legado_cenario(ncm='84818095', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['status'], 'IGUAL')
        self.assertEqual(r['divergencias'], [])

    def test_divergente_icms_diferente(self):
        escopo = _escopo_ncm(self.cenario, '84818096')
        _regra_saida(escopo, aliquota_icms=Decimal('18'))
        RegraFiscal.objects.create(
            ncm='84818096',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        r = comparar_regra_fiscal_saida_legado_cenario(ncm='84818096', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['status'], 'DIVERGENTE')
        campos = {d['campo'] for d in r['divergencias']}
        self.assertIn('aliquota_icms', campos)

    def test_cenario_nao_encontrado(self):
        RegraFiscal.objects.create(
            ncm='84818097',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        r = comparar_regra_fiscal_saida_legado_cenario(ncm='84818097', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['status'], 'CENARIO_NAO_ENCONTRADO')
        self.assertTrue(r['legado']['encontrado'])
        self.assertFalse(r['cenario']['encontrado'])

    def test_legado_nao_encontrado(self):
        escopo = _escopo_ncm(self.cenario, '84818098')
        _regra_saida(escopo)
        r = comparar_regra_fiscal_saida_legado_cenario(ncm='84818098', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['status'], 'LEGADO_NAO_ENCONTRADO')
        self.assertTrue(r['cenario']['encontrado'])
        self.assertFalse(r['legado']['encontrado'])

    def test_ambos_nao_encontrados(self):
        r = comparar_regra_fiscal_saida_legado_cenario(ncm='00000000', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['status'], 'AMBOS_NAO_ENCONTRADOS')

    def test_decimais_equivalentes_iguais(self):
        escopo = _escopo_ncm(self.cenario, '84818099')
        _regra_saida(escopo, aliquota_icms=Decimal('18.0000'))
        RegraFiscal.objects.create(
            ncm='84818099',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            cst_icms='00',
            aliquota_icms=18,
            cst_ipi='50',
            aliquota_ipi=5.0,
            cst_pis='01',
            aliquota_pis=1.65,
            cst_cofins='01',
            aliquota_cofins=7.6,
        )
        r = comparar_regra_fiscal_saida_legado_cenario(ncm='84818099', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['status'], 'IGUAL')

    def test_origem_oficial_legado_com_flag_false(self):
        escopo = _escopo_ncm(self.cenario, '84818100')
        _regra_saida(escopo, aliquota_icms=Decimal('99'))
        legado = RegraFiscal.objects.create(
            ncm='84818100',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False):
            r = comparar_regra_fiscal_saida_legado_cenario(ncm='84818100', uf_origem='SP', uf_destino='RJ')
            self.assertEqual(r['origem_oficial_proposta'], 'LEGADO')
            fb = find_regra_fiscal_saida_com_fallback('84818100', 'SP', 'RJ', 'Saída')
            self.assertEqual(fb['origem'], 'LEGADO')
            self.assertEqual(fb['regra_legada_id'], legado.id)


class CompararSaidaFiscalAPITests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('cmp_api', 'cmp@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = garantir_cenario_saida_padrao()
        self.url = reverse('regrafiscal-saida-comparar')

    def test_endpoint_200_divergente(self):
        escopo = _escopo_ncm(self.cenario, '84818101')
        _regra_saida(escopo, aliquota_icms=Decimal('18'), cfop_venda='6102')
        RegraFiscal.objects.create(
            ncm='84818101',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        r = self.client.get(self.url, {'ncm': '84818101', 'uf_origem': 'SP', 'uf_destino': 'RJ'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['status'], 'DIVERGENTE')
        self.assertTrue(len(body['divergencias']) >= 1)
        labels = {d['campo'] for d in body['divergencias']}
        self.assertTrue('aliquota_icms' in labels or 'cfop' in labels)

    def test_endpoint_200_ambos_nao_encontrados(self):
        r = self.client.get(self.url, {'ncm': '00000001', 'uf_origem': 'SP', 'uf_destino': 'RJ'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], 'AMBOS_NAO_ENCONTRADOS')

    def test_buscar_com_fallback_inalterado(self):
        escopo = _escopo_ncm(self.cenario, '84818102')
        regra = _regra_saida(escopo)
        url_buscar = reverse('regrafiscal-saida-buscar')
        r = self.client.get(url_buscar, {'ncm': '84818102', 'uf_origem': 'SP', 'uf_destino': 'RJ'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r.json()['regra_id'], regra.id)

    def test_legado_buscar_inalterado(self):
        legado = RegraFiscal.objects.create(
            ncm='87654321',
            uf_origem='SP',
            uf_destino='MG',
            operacao='Saída',
            cfop='6102',
            aliquota_icms=12.0,
        )
        url = reverse('regrafiscal-buscar')
        r = self.client.get(
            url,
            {'ncm': '87654321', 'uf_origem': 'SP', 'uf_destino': 'MG', 'operacao': 'Saída'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['id'], legado.id)
