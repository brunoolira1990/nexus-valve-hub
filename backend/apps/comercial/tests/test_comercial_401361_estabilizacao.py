"""ERP 4.0.13.6.1 — regressão integrada Pedido → Faturamento → NF-e (estabilização)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import (
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
    estornar_faturamento_pedido,
    montar_resumo_faturamento,
)
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.comercial.serializers import PedidoVendaSerializer, recalcular_pedido_venda
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _setup_pedido_qtd_2() -> tuple[PedidoVenda, ItemPedidoVenda]:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
    fam = FamiliaProduto.objects.create(
        codigo_figura='F1',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao='Flange',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo='FL-001',
        unidade='PC',
        ncm='84818200',
    )
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=Decimal('0'),
    )
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('2'),
        quantidade_negociada=Decimal('2'),
        valor_unitario=Decimal('250'),
        preco_por_unidade_negociada=Decimal('250'),
        desconto=Decimal('0'),
    )
    recalcular_pedido_venda(pedido)
    pedido.refresh_from_db()
    return pedido, item


class Comercial401361EstabilizacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('401361', '401361@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_cenario_a_pedido_aberto_quantidade_2_total_500(self):
        pedido, item = _setup_pedido_qtd_2()
        self.assertEqual(pedido.valor_total, Decimal('500.00'))
        data = PedidoVendaSerializer(pedido).data
        self.assertEqual(Decimal(str(data['itens'][0]['quantidade'])), Decimal('2'))

    def test_cenario_b_faturamento_bate_total_pedido(self):
        pedido, item = _setup_pedido_qtd_2()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        resumo = montar_resumo_faturamento(pedido)
        self.assertEqual(resumo['valor_faturado'], '500.00')
        self.assertEqual(resumo['valor_pendente'], '0.00')
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'FATURADO')

    def test_cenario_c_estorno_volta_pedido_editavel(self):
        pedido, item = _setup_pedido_qtd_2()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        estornar_faturamento_pedido(
            pedido,
            criado['faturamento_id'],
            motivo='Estorno de teste automatizado do pedido',
        )
        pedido.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(pedido.status, 'ABERTO')
        self.assertEqual(item.quantidade_faturada, Decimal('0'))

    def test_cenario_d_gerar_nfe_vincula_faturamento(self):
        pedido, item = _setup_pedido_qtd_2()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        r = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        self.assertEqual(fat.nfe_saida_id, r['nfe_saida_id'])
        resumo = montar_resumo_faturamento(pedido)
        self.assertFalse(resumo.get('tem_inconsistencia_fiscal'))

    def test_api_estornar_faturamento(self):
        pedido, item = _setup_pedido_qtd_2()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        res = self.client.post(
            f'/api/pedidos-venda/{pedido.pk}/faturamentos/{criado["faturamento_id"]}/estornar/',
            {'motivo': 'Estorno via API de teste automatizado'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'ABERTO')
