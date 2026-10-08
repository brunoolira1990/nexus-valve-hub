"""Comercial/NF-e 3.4 — origem comercial travada e dados complementares."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.cadastros.models import Transportadora
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.produtos.models import Produto
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_efeitos import aplicar_efeitos_autorizacao_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item


class NFeSaidaBloqueio34Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe34', 'nfe34@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _gerar_nf_faturamento(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.prefetch_related('itens__produto', 'itens__item_faturamento_pedido').get(
            pk=r['nfe_saida_id'],
        )
        return pedido, item, nf

    def test_nf_faturamento_produto_correto_do_item(self):
        pedido, item_pedido = _pedido_item()
        produto_b = Produto.objects.create(
            familia=item_pedido.produto.familia,
            descricao='Produto B 34',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='PV34-B',
            unidade='PC',
            ncm='84818200',
        )
        self.assertNotEqual(produto_b.pk, item_pedido.produto_id)

        fat = _faturamento_pronto(pedido, item_pedido)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf_item = ItemNFeSaida.objects.select_related('item_faturamento_pedido', 'produto').get(
            nf_id=r['nfe_saida_id'],
        )
        self.assertEqual(nf_item.produto_id, item_pedido.produto_id)
        self.assertEqual(nf_item.item_faturamento_pedido.produto_id, item_pedido.produto_id)
        self.assertNotEqual(nf_item.produto_id, produto_b.pk)

    def test_nf_faturamento_bloqueia_editar_itens(self):
        _pedido, _item, nf = self._gerar_nf_faturamento()
        nf_item = nf.itens.first()
        ser = NFeSaidaSerializer(
            nf,
            data={
                'numero': nf.numero,
                'data': nf.data.isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [
                    {
                        'produto_id': nf_item.produto_id,
                        'quantidade': str(nf_item.quantidade),
                        'valor': str(nf_item.valor + Decimal('1')),
                    },
                ],
            },
            partial=True,
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('itens', ser.errors)

    def test_nf_faturamento_permite_dados_complementares_rascunho(self):
        _pedido, _item, nf = self._gerar_nf_faturamento()
        transp = Transportadora.objects.create(razao_social='Transp 34', cnpj='44.555.666/0001-77')
        resp = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {
                'transportadora_id': transp.pk,
                'modalidade_frete': '0',
                'valor_frete': '150.00',
                'quantidade_volumes': 2,
                'peso_bruto': '100.5',
                'peso_liquido': '95.2',
                'observacoes_nfe': 'Entrega agendada',
                'informacoes_adicionais': 'Info compl.',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        nf.refresh_from_db()
        self.assertEqual(nf.transportadora_id, transp.pk)
        self.assertEqual(nf.modalidade_frete, '0')
        self.assertEqual(nf.valor_frete, Decimal('150.00'))
        self.assertEqual(nf.observacoes_nfe, 'Entrega agendada')

    def test_nf_manual_rascunho_permite_item(self):
        pedido, item = _pedido_item()
        ser = NFeSaidaSerializer(
            data={
                'numero': 'MANUAL-34',
                'cliente_id': pedido.cliente_id,
                'data': pedido.data.isoformat(),
                'status': 'RASCUNHO',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
                'itens': [{'produto_id': item.produto_id, 'quantidade': '1', 'valor': '10'}],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        self.assertIsNone(nf.faturamento_pedido_venda_id)
        self.assertEqual(nf.itens.count(), 1)

    def test_nf_autorizada_bloqueia_complementares(self):
        _pedido, _item, nf = self._gerar_nf_faturamento()
        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=self.user)
        nf.refresh_from_db()
        ser = NFeSaidaSerializer(
            nf,
            data={'observacoes_nfe': 'Tentativa após autorização'},
            partial=True,
        )
        self.assertFalse(ser.is_valid())

    def test_api_listagem_flags_origem_travada(self):
        _pedido, _item, nf = self._gerar_nf_faturamento()
        det = self.client.get(f'/api/nf-saidas/{nf.pk}/').json()
        self.assertTrue(det['origem_comercial_travada'])
        self.assertTrue(det['dados_complementares_editaveis'])
        self.assertFalse(det['itens_comerciais_editaveis'])
