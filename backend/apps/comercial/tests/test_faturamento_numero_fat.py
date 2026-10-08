"""Numeração FAT-YYYYMMDD-NNNN independente do PV."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.comercial.numbering import gerar_numero_faturamento
from apps.produtos.models import FamiliaProduto, Produto


def _pedido(numero: str, *, data: date | None = None) -> PedidoVenda:
    emp = Empresa.objects.create(
        razao_social='Emp FAT',
        cnpj='11222333000144',
        uf='SP',
        cidade='São Paulo',
        logradouro='Rua',
        numero='1',
        bairro='Centro',
        cep='01001000',
    )
    cli = Cliente.objects.create(
        razao_social='Cli FAT',
        cnpj='99888777000166',
        uf='SP',
        cidade='São Paulo',
        logradouro='Av',
        numero='2',
        bairro='Centro',
        cep='01001000',
    )
    return PedidoVenda.objects.create(
        numero=numero,
        empresa_emitente=emp,
        cliente=cli,
        data=data or date.today(),
        status='ABERTO',
        valor_total=Decimal('100'),
    )


def _item(pedido: PedidoVenda) -> ItemPedidoVenda:
    fam = FamiliaProduto.objects.create(
        codigo_figura='FAT1',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao='Prod FAT',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo='FAT-PROD',
        unidade='PC',
    )
    return ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('10'),
        quantidade_negociada=Decimal('10'),
        valor_unitario=Decimal('10'),
        preco_por_unidade_negociada=Decimal('10'),
    )


class FaturamentoNumeroFatTests(TestCase):
    def test_gerar_numero_faturamento_formato(self):
        ref = date(2026, 5, 23)
        n1 = gerar_numero_faturamento(ref)
        n2 = gerar_numero_faturamento(ref)
        self.assertRegex(n1, r'^FAT-20260523-\d{4}$')
        self.assertRegex(n2, r'^FAT-20260523-\d{4}$')
        self.assertNotEqual(n1, n2)

    def test_sequencia_diaria_reinicia_em_outra_data(self):
        d1 = date(2026, 5, 23)
        d2 = date(2026, 5, 24)
        n1 = gerar_numero_faturamento(d1)
        n2 = gerar_numero_faturamento(d2)
        self.assertTrue(n1.endswith('-0001') or n1.endswith('-00001'))
        self.assertIn('20260524', n2)

    def test_fat_independente_do_pv(self):
        pedido = _pedido('PV-20260521-0002')
        item = _item(pedido)
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
        self.assertRegex(fat.numero_faturamento, r'^FAT-\d{8}-\d{4}$')
        self.assertNotEqual(fat.numero_faturamento, pedido.numero)

    def test_um_pv_pode_ter_varios_fats(self):
        pedido = _pedido('PV-20260521-0003')
        item = _item(pedido)
        ids = []
        for qtd in ('2', '3'):
            criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': qtd}]})
            confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
            ids.append(criado['faturamento_id'])
        nums = list(
            FaturamentoPedidoVenda.objects.filter(pk__in=ids).values_list('numero_faturamento', flat=True),
        )
        self.assertEqual(len(set(nums)), 2)
        for n in nums:
            self.assertTrue(n.startswith('FAT-'))
