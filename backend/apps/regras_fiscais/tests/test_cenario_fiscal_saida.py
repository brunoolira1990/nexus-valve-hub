"""Fase Saída 1 — Cenário Fiscal de Saída (modelos, API, compatibilidade)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.comercial.pricing import find_regra_fiscal
from apps.regras_fiscais.cenario_fiscal_saida import (
    NOME_CENARIO_PADRAO_SAIDA,
    garantir_cenario_saida_padrao,
    gerar_label_regra_fiscal_saida,
    resumo_impostos_saida,
    status_configuracao_saida,
)
from apps.regras_fiscais.models import (
    CenarioFiscalSaida,
    CenarioFiscalSaidaEscopo,
    RegraFiscal,
    RegraFiscalEntrada,
    RegraFiscalSaida,
)


class CenarioFiscalSaidaMigrationTests(TestCase):
    def test_cenario_padrao_saida_existe(self):
        cenario = CenarioFiscalSaida.objects.filter(padrao=True, ativo=True).first()
        self.assertIsNotNone(cenario)
        self.assertEqual(cenario.nome, NOME_CENARIO_PADRAO_SAIDA)

    def test_garantir_cenario_idempotente(self):
        c1 = garantir_cenario_saida_padrao()
        c2 = garantir_cenario_saida_padrao()
        self.assertEqual(c1.pk, c2.pk)


class CenarioFiscalSaidaModelTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()

    def test_criar_escopo_ncm(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        self.assertEqual(escopo.tipo_escopo, 'NCM')
        self.assertEqual(escopo.ncm, '84818095')

    def test_regra_saida_vincula_cenario_e_escopo(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='73071100',
        )
        regra = RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            cfop_venda='5102',
            uf_origem='SP',
            uf_destino='RJ',
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE,
            cst_icms='00',
            aliquota_icms=Decimal('18'),
            cst_ipi='50',
            aliquota_ipi=Decimal('5'),
            cst_pis='01',
            aliquota_pis=Decimal('1.65'),
            cst_cofins='01',
            aliquota_cofins=Decimal('7.6'),
            fcp_aplicavel=True,
            aliquota_fcp=Decimal('2'),
            reforma_tributaria={
                'cst_ibs_cbs': '000',
                'aliquota_cbs': '0.9',
            },
        )
        regra.refresh_from_db()
        self.assertIsNotNone(regra.cenario_id)
        self.assertEqual(regra.escopo_id, escopo.id)
        self.assertIn('NCM 73071100', regra.descricao_cenario)
        self.assertIn('5102', regra.descricao_cenario)

    def test_label_regra_saida_formato(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        regra = RegraFiscalSaida(
            escopo=escopo,
            cenario=self.cenario,
            cfop_venda='6108',
            uf_origem='SP',
            uf_destino='MG',
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE,
        )
        label = gerar_label_regra_fiscal_saida(regra, escopo)
        self.assertIn('NCM 84818095', label)
        self.assertIn('SP→MG', label)
        self.assertIn('6108', label)
        self.assertIn('Não contribuinte', label)

    def test_resumo_impostos_e_status(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.GERAL,
        )
        regra = RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            cfop_venda='5102',
            cst_icms='00',
            aliquota_icms=Decimal('12'),
        )
        resumo = resumo_impostos_saida(regra)
        self.assertIn('CST 00', resumo['icms'])
        self.assertEqual(status_configuracao_saida(regra), 'CONFIGURADO')


class RegraFiscalLegadoIntactoTests(TestCase):
    def test_regra_fiscal_atual_nao_alterada(self):
        legado = RegraFiscal.objects.create(
            ncm='12345678',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            cst_icms='00',
            aliquota_icms=18.0,
        )
        encontrada = find_regra_fiscal('12345678', 'SP', 'RJ', 'Saída')
        self.assertIsNotNone(encontrada)
        self.assertEqual(encontrada.pk, legado.pk)

    def test_entrada_nao_afetada(self):
        antes = RegraFiscalEntrada.objects.count()
        RegraFiscalEntrada.objects.create(
            nome='Entrada intacta',
            ativo=True,
            cfop_origem='1102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        self.assertEqual(RegraFiscalEntrada.objects.count(), antes + 1)


class CenarioFiscalSaidaAPITests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('saida_api', 'saida@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = garantir_cenario_saida_padrao()

    def test_lista_cenarios_saida(self):
        url = reverse('cenario-fiscal-saida-list')
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertTrue(any(c['nome'] == NOME_CENARIO_PADRAO_SAIDA for c in body))
        padrao = next(c for c in body if c['padrao'])
        self.assertIn('total_escopos', padrao)

    def test_criar_escopo_ncm_via_api(self):
        url = reverse('cenario-fiscal-saida-escopos', kwargs={'pk': self.cenario.pk})
        r = self.client.post(
            url,
            {'tipo_escopo': 'NCM', 'ncm': '84811000', 'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['ncm'], '84811000')

    def test_crud_regra_fiscal_saida(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        url = reverse('regrafiscal-saida-list')
        payload = {
            'escopo_id': escopo.id,
            'cenario_id': self.cenario.id,
            'ativo': True,
            'prioridade': 10,
            'uf_origem': 'SP',
            'uf_destino': 'RJ',
            'cfop_venda': '5102',
            'destinatario_contribuinte': 'CONTRIBUINTE',
            'tipo_operacao': 'VENDA',
            'cst_icms': '00',
            'aliquota_icms': '18.0000',
            'cst_ipi': '50',
            'aliquota_ipi': '5.0000',
            'cst_pis': '01',
            'aliquota_pis': '1.6500',
            'cst_cofins': '01',
            'aliquota_cofins': '7.6000',
            'fcp_aplicavel': True,
            'aliquota_fcp': '2.0000',
            'reforma_tributaria': {'cst_ibs_cbs': '000', 'aliquota_cbs': '0.9'},
            'movimenta_estoque': True,
            'gera_financeiro': True,
        }
        r = self.client.post(url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        regra_id = r.json()['id']
        self.assertIn('label_configuracao', r.json())
        self.assertEqual(r.json()['status_configuracao'], 'CONFIGURADO')
        self.assertTrue(r.json()['resumo_impostos']['icms'])

        r2 = self.client.get(reverse('regrafiscal-saida-detail', kwargs={'pk': regra_id}))
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

        url_cfg = reverse(
            'cenario-fiscal-saida-configuracoes-escopo',
            kwargs={'pk': self.cenario.pk, 'escopo_id': escopo.pk},
        )
        r3 = self.client.get(url_cfg)
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertTrue(any(c['id'] == regra_id for c in r3.json()))

    def test_matriz_escopo(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            cfop_venda='5102',
            uf_origem='SP',
            uf_destino='RJ',
            cst_icms='00',
            aliquota_icms=Decimal('18'),
        )
        url = reverse(
            'cenario-fiscal-saida-matriz-escopo',
            kwargs={'pk': self.cenario.pk, 'escopo_id': escopo.pk},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['escopo']['ncm'], '84818095')
        self.assertEqual(len(body['configuracoes']), 1)
        self.assertEqual(body['configuracoes'][0]['cfop_venda'], '5102')

    def test_regras_fiscais_legado_api(self):
        RegraFiscal.objects.create(
            ncm='87654321',
            uf_origem='SP',
            uf_destino='MG',
            operacao='Saída',
            cfop='6102',
            aliquota_icms=12.0,
        )
        url = reverse('regrafiscal-list')
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x['ncm'] == '87654321' for x in r.json()))

        busca = reverse('regrafiscal-buscar')
        r2 = self.client.get(
            busca,
            {'ncm': '87654321', 'uf_origem': 'SP', 'uf_destino': 'MG', 'operacao': 'Saída'},
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
