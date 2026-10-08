"""Conferência NF-e histórica: vínculo linha ↔ item do pedido de compra (Fase 2.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _setup_nf_pedido(suffix: str):
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj())
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    pedido = PedidoCompra.objects.create(
        numero=f'PC-{suffix}',
        fornecedor=forn,
        data=date(2026, 1, 15),
    )
    item_pc = ItemPedidoCompra.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('10.000'),
        quantidade_negociada=Decimal('10.000'),
        unidade_negociada='PC',
        valor_unitario=Decimal('25.50'),
        valor_total_item=Decimal('255.00'),
    )
    pedido_outro = PedidoCompra.objects.create(
        numero=f'PC-OUT-{suffix}',
        fornecedor=forn,
        data=date(2026, 1, 10),
    )
    item_pc_outro = ItemPedidoCompra.objects.create(
        pedido=pedido_outro,
        produto=prod,
        quantidade=Decimal('1.000'),
        unidade_negociada='PC',
        valor_unitario=Decimal('1.00'),
        valor_total_item=Decimal('1.00'),
    )
    dh = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'35{suffix}'[:44].ljust(44, '0'),
        numero=f'NF{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=dh,
        valor_total_nf=Decimal('255.00'),
        fornecedor_emitente=forn,
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=1,
        prod_json={
            'cProd': f'COD-{suffix}',
            'xProd': f'Produto {suffix}',
            'qCom': '10.000',
            'uCom': 'PC',
            'vUnCom': '25.50',
            'vProd': '255.00',
            'NCM': '84818099',
        },
    )
    conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=nf)
    conf.pedido_compra = pedido
    conf.save(update_fields=['pedido_compra'])
    item_conf, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
    user = get_user_model().objects.create_user(f'conf_{suffix}', f'{suffix}@test.com', 'x')
    client = APIClient()
    client.force_authenticate(user)
    url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': nf.id})
    return {
        'client': client,
        'url': url,
        'conf': conf,
        'item_conf': item_conf,
        'pedido': pedido,
        'pedido_outro': pedido_outro,
        'item_pc': item_pc,
        'item_pc_outro': item_pc_outro,
        'prod': prod,
        'nf': nf,
    }


class ConferenciaItemPedidoCompraTests(TestCase):
    def test_salvar_item_pedido_valido(self):
        ctx = _setup_nf_pedido(uuid.uuid4().hex[:8])
        r = ctx['client'].post(
            ctx['url'],
            {
                'pedido_compra_id': ctx['pedido'].id,
                'itens': [
                    {
                        'id': ctx['item_conf'].id,
                        'produto_id': ctx['prod'].id,
                        'item_pedido_compra_id': ctx['item_pc'].id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                ],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200, r.content)
        ctx['item_conf'].refresh_from_db()
        self.assertEqual(ctx['item_conf'].item_pedido_compra_id, ctx['item_pc'].id)
        self.assertTrue(ctx['item_conf'].snapshot_pedido)
        self.assertEqual(ctx['item_conf'].snapshot_pedido.get('pedido_numero'), ctx['pedido'].numero)

    def test_item_pedido_de_outro_pedido_retorna_400(self):
        ctx = _setup_nf_pedido(uuid.uuid4().hex[:8])
        r = ctx['client'].post(
            ctx['url'],
            {
                'pedido_compra_id': ctx['pedido'].id,
                'itens': [{'id': ctx['item_conf'].id, 'item_pedido_compra_id': ctx['item_pc_outro'].id}],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 400)

    def test_sem_pedido_cabecalho_com_item_pedido_retorna_erro(self):
        ctx = _setup_nf_pedido(uuid.uuid4().hex[:8])
        ctx['conf'].pedido_compra = None
        ctx['conf'].save(update_fields=['pedido_compra'])
        r = ctx['client'].post(
            ctx['url'],
            {
                'pedido_compra_id': None,
                'itens': [{'id': ctx['item_conf'].id, 'item_pedido_compra_id': ctx['item_pc'].id}],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 400)

    def test_snapshot_pedido_preenchido(self):
        ctx = _setup_nf_pedido(uuid.uuid4().hex[:8])
        ctx['client'].post(
            ctx['url'],
            {
                'pedido_compra_id': ctx['pedido'].id,
                'itens': [{'id': ctx['item_conf'].id, 'item_pedido_compra_id': ctx['item_pc'].id}],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        ctx['item_conf'].refresh_from_db()
        snap = ctx['item_conf'].snapshot_pedido
        self.assertEqual(snap.get('codigo'), ctx['prod'].codigo_completo)
        self.assertEqual(snap.get('unidade'), 'PC')
        self.assertEqual(snap.get('valor_unitario'), '25.50')

    def test_divergencias_calculadas_com_item_pedido(self):
        suffix = uuid.uuid4().hex[:8]
        ctx = _setup_nf_pedido(suffix)
        item_nf = ctx['item_conf'].item_nfe_historico
        item_nf.prod_json = {
            **(item_nf.prod_json or {}),
            'qCom': '9.000',
        }
        item_nf.save(update_fields=['prod_json'])
        ctx['item_conf'].quantidade_nf = Decimal('9.000')
        ctx['item_conf'].save(update_fields=['quantidade_nf'])
        ctx['client'].post(
            ctx['url'],
            {
                'pedido_compra_id': ctx['pedido'].id,
                'itens': [
                    {
                        'id': ctx['item_conf'].id,
                        'produto_id': ctx['prod'].id,
                        'item_pedido_compra_id': ctx['item_pc'].id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                ],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        ctx['item_conf'].refresh_from_db()
        self.assertIn('quantidade_diferente', ctx['item_conf'].divergencias)

    def test_item_sem_pedido_continua_valido(self):
        ctx = _setup_nf_pedido(uuid.uuid4().hex[:8])
        r = ctx['client'].post(
            ctx['url'],
            {
                'pedido_compra_id': ctx['pedido'].id,
                'itens': [{'id': ctx['item_conf'].id, 'item_pedido_compra_id': None}],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        ctx['item_conf'].refresh_from_db()
        self.assertIsNone(ctx['item_conf'].item_pedido_compra_id)

    def test_trocar_pedido_cabecalho_limpa_vinculo_invalido(self):
        ctx = _setup_nf_pedido(uuid.uuid4().hex[:8])
        ctx['item_conf'].item_pedido_compra = ctx['item_pc']
        ctx['item_conf'].save(update_fields=['item_pedido_compra'])
        ctx['client'].post(
            ctx['url'],
            {'pedido_compra_id': ctx['pedido_outro'].id, 'itens': []},
            format='json',
            HTTP_HOST='localhost',
        )
        ctx['item_conf'].refresh_from_db()
        self.assertIsNone(ctx['item_conf'].item_pedido_compra_id)
