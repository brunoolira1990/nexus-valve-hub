"""NF-e Saída 3.3 — cliente, atendimento, CFOP snapshot e DANFE preview."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_efeitos import aplicar_efeitos_autorizacao_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida, gerar_preview_danfe_nfe_saida
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.snapshot_fiscal_helpers import cfop_from_snapshot_fiscal, normalize_snapshot_fiscal_for_nfe
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.produtos.models import FamiliaProduto, Produto


class NFeSaidaConsistenciaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe33', 'nfe33@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_gerar_nfe_herda_cliente_do_pedido(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        self.assertEqual(nf.cliente_id, pedido.cliente_id)
        self.assertEqual(nf.pedido_venda_id, pedido.pk)
        self.assertEqual(nf.faturamento_pedido_venda_id, fat.pk)

    def test_listagem_e_detalhe_mesmo_cliente(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        lista = self.client.get('/api/nf-saidas/')
        self.assertEqual(lista.status_code, status.HTTP_200_OK)
        rows = lista.json() if isinstance(lista.json(), list) else lista.json().get('results', lista.json())
        row = next(x for x in rows if x['id'] == r['nfe_saida_id'])
        det = self.client.get(f"/api/nf-saidas/{r['nfe_saida_id']}/")
        self.assertEqual(det.status_code, status.HTTP_200_OK)
        self.assertEqual(row['cliente_id'], pedido.cliente_id)
        self.assertEqual(det.json()['cliente_id'], pedido.cliente_id)
        self.assertEqual(row['cliente_nome'], det.json()['cliente_nome'])
        self.assertEqual(row['cliente_nome'], pedido.cliente.razao_social)

    def test_listagem_exibe_modo_atendimento(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        det = self.client.get(f"/api/nf-saidas/{r['nfe_saida_id']}/")
        self.assertEqual(det.json()['modo_atendimento_estoque'], 'IMEDIATO')
        self.assertEqual(det.json()['modo_atendimento_estoque_display'], 'Imediato')

    def test_snapshot_cfop_venda_normalizado(self):
        snap = normalize_snapshot_fiscal_for_nfe({'cfop_venda': '5102', 'ncm': '84818200'})
        self.assertEqual(snap['cfop'], '5102')
        self.assertEqual(cfop_from_snapshot_fiscal(snap), '5102')

    def test_item_sem_cfop_quando_snapshot_tem_cfop_venda(self):
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'origem_regra_fiscal_saida': 'CENARIO_SAIDA', 'ncm': '84818200', 'cfop_venda': '6102'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf_item = ItemNFeSaida.objects.get(nf_id=r['nfe_saida_id'])
        self.assertEqual(nf_item.snapshot_fiscal.get('cfop'), '6102')
        val = validar_nfe_saida_para_emissao(NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id']))
        fiscal = val.get('grupos', {}).get('fiscal', [])
        self.assertFalse(any(x.get('codigo') == 'ITEM_SEM_CFOP' for x in fiscal))

    def test_patch_nao_altera_cliente_nf_faturamento(self):
        pedido, item = _pedido_item()
        outro = Cliente.objects.create(razao_social='Outro Cliente', cnpj='11.222.333/0001-44', uf='SP')
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf_id = r['nfe_saida_id']
        resp = self.client.patch(
            f'/api/nf-saidas/{nf_id}/',
            {'cliente_id': outro.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        nf = NFeSaida.objects.get(pk=nf_id)
        self.assertEqual(nf.cliente_id, pedido.cliente_id)

    def test_patch_nf_autorizada_sem_itens_ok(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        nf.refresh_from_db()
        det = self.client.get(f'/api/nf-saidas/{nf.pk}/').json()
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'numero': det['numero'],
                'data': det['data'],
                'status': det['status'],
                'modo_atendimento_estoque': det['modo_atendimento_estoque'],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.json())

    def test_patch_nf_autorizada_com_itens_bloqueia(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.prefetch_related('itens').get(pk=r['nfe_saida_id'])
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        nf_item = nf.itens.first()
        det = self.client.get(f'/api/nf-saidas/{nf.pk}/').json()
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'numero': det['numero'],
                'data': det['data'],
                'status': det['status'],
                'modo_atendimento_estoque': det['modo_atendimento_estoque'],
                'itens': [
                    {
                        'produto_id': nf_item.produto_id,
                        'quantidade': str(nf_item.quantidade),
                        'valor': str(nf_item.valor),
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('itens', resp.json())

    def test_nfe_manual_permite_cliente(self):
        pedido, item = _pedido_item()
        cli = pedido.cliente
        ser = NFeSaidaSerializer(
            data={
                'numero': 'RASCUNHO-MANUAL-33',
                'cliente_id': cli.pk,
                'data': date.today().isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [{'produto_id': item.produto_id, 'quantidade': '1', 'valor': '10'}],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        self.assertEqual(nf.cliente_id, cli.pk)
        self.assertIsNone(nf.faturamento_pedido_venda_id)

    def test_danfe_preview_gera_sem_erro_e_menciona_cfop(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.prefetch_related('itens__produto', 'cliente', 'pedido_venda__cliente').get(
            pk=r['nfe_saida_id'],
        )
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertEqual(dados['itens'][0]['cfop'], '5102')
        pdf_bytes, meta = gerar_preview_danfe_nfe_saida(nf)
        self.assertFalse(meta.get('bloqueado'))
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
