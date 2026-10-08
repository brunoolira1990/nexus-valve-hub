"""NF-e Saída 3.5.1 — transportadora, conferência UX e diagnósticos."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Transportadora
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_conferencia_diagnostico import diagnostico_reforma_item
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item


class NFeSaida351UxTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe351', 'nfe351@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _nf_fat(self, *, reforma: bool = True):
        pedido, item = _pedido_item()
        snap = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'ncm': '84818200',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'icms_saida_percentual': '18',
        }
        if reforma:
            snap['reforma_tributaria'] = {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_cbs': '0.9',
            }
        item.snapshot_fiscal = snap
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        return NFeSaida.objects.select_related('transportadora').prefetch_related('itens').get(
            pk=r['nfe_saida_id'],
        )

    def test_transportadora_search_nome(self):
        Transportadora.objects.create(razao_social='Rápido Norte Ltda', cnpj='11.222.333/0001-44')
        r = self.client.get('/api/transportadoras/', {'search': 'Rápido', 'limit': 10})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        nomes = [x['razao_social'] for x in r.json()]
        self.assertTrue(any('Rápido' in n for n in nomes))

    def test_transportadora_search_cnpj_digitos(self):
        Transportadora.objects.create(razao_social='Transp CNPJ', cnpj='99.888.777/0001-66')
        r = self.client.get('/api/transportadoras/', {'search': '888.777', 'limit': 10})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(r.json()), 1)

    def test_criar_transportadora_api(self):
        r = self.client.post(
            '/api/transportadoras/',
            {'razao_social': 'Nova Transp 351', 'cnpj': '55.666.777/0001-88', 'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertIn('351', r.data['razao_social'])

    def test_nf_salva_transportadora_rascunho(self):
        nf = self._nf_fat()
        transp = Transportadora.objects.create(razao_social='Transp NF', cnpj='22.333.444/0001-55')
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'transportadora_id': transp.pk,
                'modalidade_frete': '0',
                'valor_frete': '250.00',
                'quantidade_volumes': 3,
                'peso_bruto': '120.5',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        nf.refresh_from_db()
        self.assertEqual(nf.transportadora_id, transp.pk)
        self.assertEqual(str(nf.modalidade_frete), '0')

    def test_conferencia_retorna_transportadora(self):
        nf = self._nf_fat()
        transp = Transportadora.objects.create(razao_social='Conf Transp', cnpj='33.444.555/0001-66')
        nf.transportadora = transp
        nf.modalidade_frete = '1'
        nf.save(update_fields=['transportadora', 'modalidade_frete'])
        conf = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf['transporte']['transportadora_id'], transp.pk)
        self.assertIn('Conf Transp', conf['transporte']['transportadora_nome'])

    def test_preview_dados_transportadora(self):
        nf = self._nf_fat()
        transp = Transportadora.objects.create(razao_social='Preview Transp SA', cnpj='44.555.666/0001-77')
        nf.transportadora = transp
        nf.modalidade_frete = '0'
        nf.valor_frete = Decimal('99.90')
        nf.save(update_fields=['transportadora', 'modalidade_frete', 'valor_frete'])
        dados = gerar_dados_preview_nfe_saida(nf)
        transp_dict = dados.get('transporte') or {}
        self.assertEqual(transp_dict.get('transportadora_nome'), 'Preview Transp SA')

    def test_reforma_diagnostico_sem_bloco(self):
        nf = self._nf_fat(reforma=False)
        item = nf.itens.first()
        diag = diagnostico_reforma_item(nf, item, item.snapshot_fiscal or {}, None)
        self.assertTrue(diag)

    def test_conferencia_reforma_diagnostico_no_item(self):
        nf = self._nf_fat(reforma=False)
        conf = montar_conferencia_nfe_saida(nf)
        row = conf['reforma_tributaria']['itens'][0]
        self.assertTrue(row.get('diagnostico'))

    def test_fiscal_alertas_gerais_zerados(self):
        nf = self._nf_fat(reforma=False)
        conf = montar_conferencia_nfe_saida(nf)
        alertas = conf['fiscal_atual'].get('alertas_gerais') or []
        self.assertTrue(any('zerados' in a.lower() for a in alertas))

    def test_nf_autorizada_bloqueia_transporte(self):
        nf = self._nf_fat()
        nf.status = 'AUTORIZADA_INTERNA'
        nf.save(update_fields=['status'])
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {'transportadora_id': None, 'modalidade_frete': '9'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
