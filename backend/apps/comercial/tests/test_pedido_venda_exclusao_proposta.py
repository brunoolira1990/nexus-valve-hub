"""Exclusão de pedido de venda — reversão de itens da proposta vinculada."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.comercial.commercial_defaults import STATUS_ITEM_CONVERTIDO, STATUS_ITEM_PENDENTE
from apps.comercial.converter_proposta_pedido import (
    converter_proposta_em_pedido_venda,
    gerar_pedido_venda_de_proposta,
)
from apps.comercial.faturamento_pedido_venda import criar_faturamento_pedido
from apps.comercial.models import PedidoVenda, PropostaComercialHistorico
from apps.comercial.pedido_venda_exclusao import excluir_pedido_venda, validar_exclusao_pedido_venda
from apps.comercial.proposta_comercial_status import item_pode_converter, status_item_proposta
from apps.comercial.tests.test_converter_proposta_pedido import (
    _item,
    _produto,
    _proposta_aprovada,
)


class PedidoVendaExclusaoPropostaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pv_exc', 'pv_exc@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_excluir_pedido_reverte_item_proposta_para_pendente(self):
        p = _proposta_aprovada()
        prod = _produto()
        item = _item(p, prod)
        item.snapshot_produto = {'fiscal_teste': {'icms': '18'}}
        item.save(update_fields=['snapshot_produto'])

        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        item.refresh_from_db()
        self.assertEqual(status_item_proposta(item), STATUS_ITEM_CONVERTIDO)
        pedido_numero = pedido.numero

        excluir_pedido_venda(pedido, usuario=self.user)

        item.refresh_from_db()
        p.refresh_from_db()
        self.assertFalse(PedidoVenda.objects.filter(pk=r['pedido_id']).exists())
        self.assertEqual(item.status_comercial, STATUS_ITEM_PENDENTE)
        self.assertIsNone(item.pedido_venda_gerado_id)
        self.assertIsNone(item.item_pedido_venda_gerado_id)
        self.assertIsNone(item.convertido_em)
        self.assertIsNone(item.convertido_por)
        self.assertTrue(item_pode_converter(item))
        self.assertEqual((item.snapshot_produto or {}).get('fiscal_teste'), {'icms': '18'})
        self.assertEqual(
            (item.snapshot_produto or {}).get('comercial', {}).get('status_comercial'),
            STATUS_ITEM_PENDENTE,
        )
        self.assertEqual(p.status, 'Aprovada')

        evt = PropostaComercialHistorico.objects.filter(
            proposta=p,
            tipo_evento=PropostaComercialHistorico.TipoEvento.PEDIDO_EXCLUIDO_STATUS_REVERTIDO,
        ).first()
        self.assertIsNotNone(evt)
        self.assertIn(pedido_numero, evt.descricao)
        self.assertEqual(evt.dados_json['pedido_id'], r['pedido_id'])
        self.assertEqual(len(evt.dados_json['itens_revertidos']), 1)

    def test_apos_excluir_pode_gerar_novo_pedido(self):
        p = _proposta_aprovada()
        item = _item(p, _produto())
        r1 = converter_proposta_em_pedido_venda(p)
        excluir_pedido_venda(PedidoVenda.objects.get(pk=r1['pedido_id']), usuario=self.user)

        r2 = converter_proposta_em_pedido_venda(p)
        self.assertNotEqual(r1['pedido_id'], r2['pedido_id'])
        item.refresh_from_db()
        self.assertEqual(status_item_proposta(item), STATUS_ITEM_CONVERTIDO)

    def test_excluir_pedido_parcial_reverte_apenas_itens_vinculados(self):
        p = _proposta_aprovada()
        item1 = _item(p, _produto())
        item2 = _item(p, _produto())
        r1 = gerar_pedido_venda_de_proposta(
            p,
            itens_payload=[{'proposta_item_id': item1.pk}],
            acao_itens_nao_selecionados='MANTER_PENDENTE',
        )
        gerar_pedido_venda_de_proposta(
            p,
            itens_payload=[{'proposta_item_id': item2.pk}],
            acao_itens_nao_selecionados='MANTER_PENDENTE',
        )
        excluir_pedido_venda(PedidoVenda.objects.get(pk=r1['pedido_id']), usuario=self.user)

        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(status_item_proposta(item1), STATUS_ITEM_PENDENTE)
        self.assertEqual(status_item_proposta(item2), STATUS_ITEM_CONVERTIDO)

    def test_api_delete_reverte_item(self):
        p = _proposta_aprovada()
        item = _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        resp = self.client.delete(f'/api/pedidos-venda/{r["pedido_id"]}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, resp.content)
        item.refresh_from_db()
        self.assertEqual(status_item_proposta(item), STATUS_ITEM_PENDENTE)

    def test_bloqueia_exclusao_com_faturamento_rascunho(self):
        from apps.comercial.tests.test_faturamento_pedido_venda import _pedido_com_itens

        pedido, item = _pedido_com_itens(qtd=Decimal('2'))
        criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.id, 'quantidade': '1'}]},
            usuario=self.user,
        )
        with self.assertRaises(ValidationError) as ctx:
            validar_exclusao_pedido_venda(pedido)
        self.assertIn('faturamento', str(ctx.exception.detail).lower())

    def test_bloqueia_exclusao_api_com_faturamento(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        pv_item = pedido.itens.get()
        criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': pv_item.id, 'quantidade': '1'}]},
            usuario=self.user,
        )
        resp = self.client.delete(f'/api/pedidos-venda/{pedido.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.content)
        self.assertIn('faturamento', str(resp.json()).lower())
