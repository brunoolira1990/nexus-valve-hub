"""NF-e Saída 3.5 — conferência fiscal, reforma e pedido do cliente."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida, gerar_preview_danfe_nfe_saida
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item


class NFeSaidaConferencia35Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe35', 'nfe35@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _nf_fat(self):
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'ncm': '84818200',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'icms_saida_percentual': '18',
            'cst_pis': '01',
            'pis_saida_percentual': '1.65',
            'cst_cofins': '01',
            'cofins_saida_percentual': '7.6',
            'deduzir_icms_base_pis': True,
            'reforma_tributaria': {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_cbs': '0.9',
                'aliquota_ibs_estadual': '0.1',
            },
        }
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        return NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id']), item

    def test_endpoint_conferencia_retorna_ncm_cfop(self):
        nf, _item = self._nf_fat()
        resp = self.client.get(f'/api/nf-saidas/{nf.pk}/conferencia/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body['itens'][0]['ncm'], '84818200')
        self.assertEqual(body['itens'][0]['cfop'], '5102')
        self.assertIn('fiscal_atual', body['itens'][0])
        self.assertTrue(body['permissoes']['origem_comercial_travada'])

    def test_conferencia_reforma_tributaria(self):
        nf, _item = self._nf_fat()
        conf = montar_conferencia_nfe_saida(nf)
        self.assertEqual(conf['reforma_tributaria']['resumo']['status'], 'OK')
        self.assertEqual(conf['reforma_tributaria']['itens'][0]['dados']['cst_ibs_cbs'], '000')

    def test_pedido_cliente_salva_cabecalho_e_item(self):
        nf, _item = self._nf_fat()
        nf_item = nf.itens.first()
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'pedido_cliente_numero': 'OC-2026-100',
                'itens': [
                    {
                        'id': nf_item.pk,
                        'pedido_cliente_numero': 'OC-2026-100',
                        'pedido_cliente_item': '10',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        nf.refresh_from_db()
        nf_item.refresh_from_db()
        self.assertEqual(nf.pedido_cliente_numero, 'OC-2026-100')
        self.assertEqual(nf_item.pedido_cliente_item, '10')

    def test_faturamento_bloqueia_produto_no_patch(self):
        nf, _item = self._nf_fat()
        nf_item = nf.itens.first()
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'itens': [
                    {
                        'id': nf_item.pk,
                        'produto_id': nf_item.produto_id,
                        'quantidade': '99',
                        'valor': '1',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validacao_grupo_reforma(self):
        nf, _item = self._nf_fat()
        conf = montar_conferencia_nfe_saida(nf, modo='completo', incluir_checklist=True)
        grupos = conf['checklist'].get('grupos', {})
        self.assertIn('reforma_tributaria', grupos)

    def test_preview_dados_pedido_cliente(self):
        nf, _item = self._nf_fat()
        nf.pedido_cliente_numero = 'PO-CLIENTE'
        nf.save(update_fields=['pedido_cliente_numero'])
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertEqual(dados['pedido_cliente_numero'], 'PO-CLIENTE')
        self.assertTrue(dados['itens'][0].get('pedido_cliente'))

    def test_observacoes_internas_nao_vao_preview(self):
        nf, _item = self._nf_fat()
        nf.observacoes_internas = 'Segredo interno ERP'
        nf.observacoes_nfe = 'Texto DANFE'
        nf.save(update_fields=['observacoes_internas', 'observacoes_nfe'])
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertIn('Texto DANFE', dados['observacoes'])
        self.assertNotIn('Segredo interno', dados['observacoes'])
        self.assertNotIn('Segredo interno', dados['informacoes_adicionais'])

    def test_danfe_gera_com_reforma(self):
        nf, _item = self._nf_fat()
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertTrue(dados['itens'][0].get('reforma_tributaria'))
        pdf, meta = gerar_preview_danfe_nfe_saida(nf)
        self.assertFalse(meta.get('bloqueado'))
        self.assertTrue(pdf.startswith(b'%PDF'))
