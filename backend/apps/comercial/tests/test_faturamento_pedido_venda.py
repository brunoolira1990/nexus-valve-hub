"""Pedido Venda 3 — faturamento parcial do pedido de venda."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.converter_proposta_pedido import converter_proposta_em_pedido_venda
from apps.comercial.faturamento_pedido_venda import (
    cancelar_faturamento_pedido,
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
    estornar_faturamento_pedido,
    montar_resumo_faturamento,
    reparar_vinculo_faturamento_nfe,
)
from apps.comercial.models import (
    FaturamentoPedidoVenda,
    ItemPedidoVenda,
    ItemProposta,
    PedidoVenda,
    Proposta,
)
from apps.fiscal.models import AtendimentoEstoque, NFeSaida
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod fat',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PF-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_com_itens(*, qtd=Decimal('10'), preco=Decimal('100'), desconto=Decimal('0')) -> tuple[PedidoVenda, ItemPedidoVenda]:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=Decimal('1000'),
    )
    prod = _produto()
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=qtd,
        quantidade_negociada=qtd,
        valor_unitario=preco,
        preco_por_unidade_negociada=preco,
        desconto=desconto,
        snapshot_fiscal={'origem_regra_fiscal_saida': 'LEGADO', 'ncm': '84818200'},
    )
    return pedido, item


class FaturamentoPedidoVendaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fat_pv', 'fat@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_resumo_mostra_quantidade_pendente(self):
        pedido, item = _pedido_com_itens()
        resumo = montar_resumo_faturamento(pedido)
        self.assertEqual(resumo['pedido_id'], pedido.pk)
        self.assertEqual(len(resumo['itens']), 1)
        row = resumo['itens'][0]
        self.assertEqual(row['item_pedido_id'], item.pk)
        self.assertEqual(row['quantidade_pendente'], '10.000')
        self.assertEqual(row['status_item'], ItemPedidoVenda.StatusItem.PENDENTE)

    def test_criar_faturamento_parcial(self):
        pedido, item = _pedido_com_itens()
        r = criar_faturamento_pedido(
            pedido,
            {'observacao': 'Parcial', 'itens': [{'item_pedido_id': item.pk, 'quantidade': '4'}]},
        )
        self.assertEqual(r['itens_criados'], 1)
        fat = FaturamentoPedidoVenda.objects.get(pk=r['faturamento_id'])
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.RASCUNHO)
        linha = fat.itens.get()
        self.assertEqual(linha.quantidade, Decimal('4'))
        self.assertEqual(linha.snapshot_fiscal['origem_regra_fiscal_saida'], 'LEGADO')
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, Decimal('0'))

    def test_criar_acima_saldo_bloqueia(self):
        pedido, item = _pedido_com_itens()
        with self.assertRaises(ValueError) as ctx:
            criar_faturamento_pedido(
                pedido,
                {'itens': [{'item_pedido_id': item.pk, 'quantidade': '11'}]},
            )
        self.assertIn('excede', str(ctx.exception).lower())

    def test_confirmar_atualiza_quantidade_faturada(self):
        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '4'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, Decimal('4'))
        self.assertEqual(item.status_item, ItemPedidoVenda.StatusItem.PARCIAL)

    def test_confirmar_parcial_status_pedido(self):
        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '4'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PARCIALMENTE_FATURADO')

    def test_confirmar_total_status_faturado(self):
        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '10'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        pedido.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(pedido.status, 'FATURADO')
        self.assertEqual(item.status_item, ItemPedidoVenda.StatusItem.FATURADO)

    def test_pedido_cancelado_bloqueia(self):
        pedido, item = _pedido_com_itens()
        pedido.status = 'CANCELADO'
        pedido.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '1'}]})

    def test_item_cancelado_bloqueia(self):
        pedido, item = _pedido_com_itens()
        item.status_item = ItemPedidoVenda.StatusItem.CANCELADO
        item.save(update_fields=['status_item'])
        with self.assertRaises(ValueError):
            criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '1'}]})

    def test_nao_duplica_quantidade_faturada(self):
        pedido, item = _pedido_com_itens()
        c1 = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '6'}]})
        confirmar_faturamento_pedido(pedido, c1['faturamento_id'])
        with self.assertRaises(ValueError):
            criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '6'}]})

    def test_cancelar_rascunho_nao_altera_faturada(self):
        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '3'}]})
        cancelar_faturamento_pedido(pedido, criado['faturamento_id'])
        item.refresh_from_db()
        self.assertEqual(item.quantidade_faturada, Decimal('0'))

    def test_cancelar_confirmado_bloqueia(self):
        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        with self.assertRaises(ValueError) as ctx:
            cancelar_faturamento_pedido(pedido, criado['faturamento_id'])
        self.assertIn('confirmado', str(ctx.exception).lower())

    def test_api_resumo_e_faturamento(self):
        pedido, item = _pedido_com_itens()
        r1 = self.client.get(f'/api/pedidos-venda/{pedido.pk}/resumo-faturamento/')
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertTrue(r1.json()['pode_faturar'])
        r2 = self.client.post(
            f'/api/pedidos-venda/{pedido.pk}/faturamentos/',
            {'itens': [{'item_pedido_id': item.pk, 'quantidade': '5'}]},
            format='json',
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        fid = r2.json()['faturamento_id']
        r3 = self.client.post(f'/api/pedidos-venda/{pedido.pk}/faturamentos/{fid}/confirmar/', {}, format='json')
        self.assertEqual(r3.status_code, status.HTTP_200_OK)

    def test_conversao_proposta_continua(self):
        emp = Empresa.objects.create(razao_social='E', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='C', cnpj=_cnpj(), uf='RJ')
        hoje = date.today()
        p = Proposta.objects.create(
            numero=f'P-{uuid.uuid4().hex[:4]}',
            data=hoje,
            validade=hoje,
            empresa_emitente=emp,
            cliente=cli,
            status='Aprovada',
        )
        prod = _produto()
        ItemProposta.objects.create(
            proposta=p,
            produto=prod,
            quantidade=Decimal('1'),
            quantidade_negociada=Decimal('1'),
            valor_unitario=Decimal('50'),
            preco_por_unidade_negociada=Decimal('50'),
        )
        r = converter_proposta_em_pedido_venda(p)
        self.assertFalse(r['ja_existia'])
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.itens.count(), 1)

    def test_nao_emite_nfe_nem_atendimento_nem_financeiro(self):
        pedido, item = _pedido_com_itens()
        nfe_antes = NFeSaida.objects.count()
        atend_antes = AtendimentoEstoque.objects.count()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        self.assertEqual(NFeSaida.objects.count(), nfe_antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)
        pedido.refresh_from_db()
        self.assertFalse(pedido.titulos_receber if hasattr(pedido, 'titulos_receber') else False)

    def test_valor_faturado_respeita_desconto_proporcional(self):
        from apps.comercial.serializers import recalcular_pedido_venda

        pedido, item = _pedido_com_itens(qtd=Decimal('2'), preco=Decimal('250'), desconto=Decimal('250'))
        recalcular_pedido_venda(pedido)
        pedido.refresh_from_db()
        self.assertEqual(pedido.valor_total, Decimal('250.00'))

        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        resumo = montar_resumo_faturamento(pedido)
        self.assertEqual(resumo['valor_faturado'], '250.00')
        self.assertEqual(resumo['valor_total_pedido'], '250.00')

    def test_estornar_faturamento_reverte_quantidade_e_status(self):
        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '10'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        estornar_faturamento_pedido(
            pedido,
            criado['faturamento_id'],
            motivo='Estorno de teste automatizado do faturamento',
        )
        item.refresh_from_db()
        pedido.refresh_from_db()
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        self.assertEqual(fat.status, FaturamentoPedidoVenda.Status.CANCELADO)
        self.assertEqual(item.quantidade_faturada, Decimal('0'))
        self.assertEqual(pedido.status, 'ABERTO')
        resumo = montar_resumo_faturamento(pedido)
        self.assertEqual(resumo['valor_faturado'], '0.00')

    def test_reparar_vinculo_orfao_gerado_nfe_sem_fk(self):
        from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento

        pedido, item = _pedido_com_itens()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        nf = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])['nfe_saida_id']
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        fat.nfe_saida_id = None
        fat.save(update_fields=['nfe_saida'])
        r = reparar_vinculo_faturamento_nfe(pedido, fat.pk)
        self.assertTrue(r['reparado'])
        fat.refresh_from_db()
        self.assertEqual(fat.nfe_saida_id, nf)
