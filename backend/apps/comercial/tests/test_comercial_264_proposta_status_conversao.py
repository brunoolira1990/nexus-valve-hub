"""Comercial 2.6.4 — status CONVERTIDA após conversão proposta → pedido de venda."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.commercial_defaults import STATUS_PROPOSTA_CONVERTIDA
from apps.comercial.converter_proposta_pedido import (
    MSG_PROPOSTA_JA_CONVERTIDA,
    converter_proposta_em_pedido_venda,
)
from apps.comercial.models import ItemProposta, PedidoVenda, Proposta
from apps.comercial.tests.test_comercial_263_proposta_externa import _pdf_text
from apps.comercial.proposta_pdf import gerar_proposta_pdf_bytes
from apps.comercial.tests.test_converter_proposta_pedido import (
    ConverterPropostaPedidoSetupMixin,
    _item,
    _produto,
    _proposta_aprovada,
)
from apps.produtos.models import FamiliaProduto, Produto


class PropostaStatusConversaoTests(ConverterPropostaPedidoSetupMixin, TestCase):
    def test_converter_altera_status_para_convertida(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        p.refresh_from_db()
        self.assertEqual(p.status, STATUS_PROPOSTA_CONVERTIDA)
        self.assertEqual(r['proposta_status'], STATUS_PROPOSTA_CONVERTIDA)

    def test_resposta_conversao_inclui_proposta_status(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        self.assertEqual(r['proposta_status'], STATUS_PROPOSTA_CONVERTIDA)
        self.assertFalse(r['ja_existia'])

    def test_listagem_retorna_status_convertida(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        converter_proposta_em_pedido_venda(p)
        r = self.client.get('/api/propostas/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = r.json() if isinstance(r.json(), list) else r.json().get('results', r.json())
        row = next(x for x in rows if x['id'] == p.pk)
        self.assertEqual(row['status'], STATUS_PROPOSTA_CONVERTIDA)
        self.assertIsNotNone(row['pedido_venda_id'])

    def test_segunda_conversao_bloqueada(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        converter_proposta_em_pedido_venda(p)
        with self.assertRaises(ValueError) as ctx:
            converter_proposta_em_pedido_venda(p)
        self.assertEqual(str(ctx.exception), MSG_PROPOSTA_JA_CONVERTIDA)
        self.assertEqual(PedidoVenda.objects.filter(proposta=p).count(), 1)

    def test_api_segunda_conversao_retorna_400(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r1 = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r1.json()['proposta_status'], STATUS_PROPOSTA_CONVERTIDA)
        r2 = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('já foi convertida', r2.json()['detail'].lower())

    def test_pedido_continua_vinculado(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.proposta_id, p.pk)

    def test_conversao_copia_prazo_entrega_texto_e_status(self):
        p = _proposta_aprovada()
        p.prazo_entrega_texto = '20 dias corridos'
        p.save(update_fields=['prazo_entrega_texto'])
        _item(p, _produto())
        r = converter_proposta_em_pedido_venda(p)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.prazo_entrega_texto, '20 dias corridos')
        p.refresh_from_db()
        self.assertEqual(p.status, STATUS_PROPOSTA_CONVERTIDA)

    def test_pdf_proposta_nao_exibe_status_interno(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        converter_proposta_em_pedido_venda(p)
        p.refresh_from_db()
        text = _pdf_text(gerar_proposta_pdf_bytes(p))
        self.assertNotIn('Convertida', text)
        self.assertNotIn('Status:', text)

    def test_sync_legado_pedido_sem_status_convertida(self):
        p = _proposta_aprovada()
        p.status = 'PENDENTE'
        p.save(update_fields=['status'])
        prod = _produto()
        _item(p, prod)
        pedido = PedidoVenda.objects.create(
            numero=f'PV-LEG-{uuid.uuid4().hex[:4]}',
            data=date.today(),
            status='ABERTO',
            cliente=p.cliente,
            empresa_emitente=p.empresa_emitente,
            proposta=p,
            valor_total=Decimal('100'),
        )
        self.assertEqual(pedido.proposta_id, p.pk)
        with self.assertRaises(ValueError):
            converter_proposta_em_pedido_venda(p)
        p.refresh_from_db()
        self.assertEqual(p.status, STATUS_PROPOSTA_CONVERTIDA)
