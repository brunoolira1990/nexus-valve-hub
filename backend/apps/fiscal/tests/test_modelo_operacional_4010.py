"""ERP 4.0.10 — modelo operacional Nexus (venda sob demanda, atendimento flexível)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import ItemPedidoCompra, ItemPedidoVenda, PedidoCompra, PedidoVenda
from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
    marcar_entrada_fiscal_conciliada,
    marcar_entrada_fiscal_pendente,
    obter_resumo_atendimento_item,
    resolver_tipo_atendimento_padrao,
)
from apps.fiscal.models import AlocacaoAtendimento, AtendimentoEstoque, EstoqueCorrida, NFeSaida
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.produtos.models import FamiliaProduto, Produto


def _produto(suffix: str) -> Produto:
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suffix}',
        unidade='PC',
        ncm='84818099',
    )


class ModeloOperacionalEnumsTests(TestCase):
    def test_enums_tipo_atendimento_existem(self):
        self.assertIn(TipoAtendimentoItem.NAO_DEFINIDO, TipoAtendimentoItem.values)
        self.assertIn(TipoAtendimentoItem.RETIRADA_FORNECEDOR, TipoAtendimentoItem.values)

    def test_enums_status_entrada_fiscal_existem(self):
        self.assertIn(StatusEntradaFiscal.PENDENTE, StatusEntradaFiscal.values)
        self.assertIn(StatusEntradaFiscal.CONCILIADA, StatusEntradaFiscal.values)

    def test_enums_origem_destino_fisico_existem(self):
        self.assertIn(OrigemFisica.FORNECEDOR, OrigemFisica.values)
        self.assertIn(DestinoFisico.CLIENTE, DestinoFisico.values)


class ModeloOperacionalHelpersTests(TestCase):
    def test_resolver_tipo_padrao_seguro(self):
        self.assertEqual(resolver_tipo_atendimento_padrao(), TipoAtendimentoItem.NAO_DEFINIDO)
        self.assertEqual(
            resolver_tipo_atendimento_padrao(tipo_atendimento='INVALIDO'),
            TipoAtendimentoItem.NAO_DEFINIDO,
        )

    def test_marcar_entrada_fiscal_helpers_nao_alteram_banco(self):
        self.assertEqual(
            marcar_entrada_fiscal_pendente()['status_entrada_fiscal'],
            StatusEntradaFiscal.PENDENTE,
        )
        self.assertEqual(
            marcar_entrada_fiscal_conciliada()['status_entrada_fiscal'],
            StatusEntradaFiscal.CONCILIADA,
        )

    def test_obter_resumo_atendimento_item(self):
        res = obter_resumo_atendimento_item(
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            quantidade_necessaria='10',
            quantidade_atendida='3',
        )
        self.assertEqual(res['tipo_atendimento'], TipoAtendimentoItem.RETIRADA_FORNECEDOR)
        self.assertEqual(res['status_entrada_fiscal'], StatusEntradaFiscal.PENDENTE)
        self.assertEqual(res['quantidade_pendente'], '7')

    def test_helpers_nao_movimentam_estoque(self):
        produto = _produto('MO1')
        estoque_antes = EstoqueCorrida.objects.filter(produto=produto).count()
        obter_resumo_atendimento_item(quantidade_necessaria='1')
        marcar_entrada_fiscal_pendente()
        self.assertEqual(EstoqueCorrida.objects.filter(produto=produto).count(), estoque_antes)


class AlocacaoAtendimentoModelTests(TestCase):
    def setUp(self):
        self.produto = _produto('AL1')
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Forn AL1',
            cnpj='11.222.333/0001-01',
        )
        self.cliente = Cliente.objects.create(
            razao_social='Cliente AL1',
            cnpj='99.888.777/0001-01',
        )
        self.pv = PedidoVenda.objects.create(numero='PV-AL1', cliente=self.cliente, data=date(2026, 5, 1))
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('100'),
        )
        self.pc = PedidoCompra.objects.create(
            numero='PC-AL1',
            fornecedor=self.fornecedor,
            data=date(2026, 5, 2),
        )
        self.item_pc = ItemPedidoCompra.objects.create(
            pedido=self.pc,
            produto=self.produto,
            quantidade=Decimal('20'),
            valor_unitario=Decimal('50'),
        )

    def test_cria_alocacao_entrada_pendente_fluxo_b(self):
        aloc = AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('5'),
            quantidade_pendente=Decimal('5'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
            origem_fisica=OrigemFisica.FORNECEDOR,
            destino_fisico=DestinoFisico.CLIENTE,
        )
        self.assertEqual(aloc.status_entrada_fiscal, StatusEntradaFiscal.PENDENTE)

    def test_cria_alocacao_entrada_conciliada_fluxo_a(self):
        aloc = AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('5'),
            quantidade_atendida=Decimal('5'),
            tipo_atendimento=TipoAtendimentoItem.ENTRADA_CONCILIADA,
            status_entrada_fiscal=StatusEntradaFiscal.CONCILIADA,
            origem_fisica=OrigemFisica.ESTOQUE_PROPRIO,
            destino_fisico=DestinoFisico.CLIENTE,
            pedido_compra_item=self.item_pc,
        )
        self.assertEqual(aloc.status_entrada_fiscal, StatusEntradaFiscal.CONCILIADA)

    def test_compra_pode_atender_multiplas_alocacoes(self):
        item_pv2 = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('3'),
            valor_unitario=Decimal('100'),
        )
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('5'),
            pedido_compra_item=self.item_pc,
            tipo_atendimento=TipoAtendimentoItem.COMPRA_VINCULADA,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=item_pv2,
            produto=self.produto,
            quantidade_necessaria=Decimal('3'),
            pedido_compra_item=self.item_pc,
            tipo_atendimento=TipoAtendimentoItem.COMPRA_VINCULADA,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        self.assertEqual(
            AlocacaoAtendimento.objects.filter(pedido_compra_item=self.item_pc).count(),
            2,
        )

    def test_item_sem_pedido_compra_vinculado(self):
        aloc = AlocacaoAtendimento.objects.create(
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.NAO_DEFINIDO,
        )
        self.assertIsNone(aloc.pedido_compra_item_id)
        self.assertIsNone(aloc.pedido_venda_item_id)

    def test_nao_movimenta_estoque_nem_atendimento_estoque(self):
        estoque_antes = EstoqueCorrida.objects.count()
        atend_antes = AtendimentoEstoque.objects.count()
        AlocacaoAtendimento.objects.create(
            produto=self.produto,
            quantidade_necessaria=Decimal('10'),
            tipo_atendimento=TipoAtendimentoItem.ESTOQUE_PROPRIO,
        )
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)

    def test_nfe_saida_nao_bloqueada_por_ausencia_entrada(self):
        """Validação existente não exige NF-e Entrada conciliada."""
        nf = NFeSaida.objects.create(
            numero='NF-MO-4010',
            cliente=self.cliente,
            data=date(2026, 5, 10),
            status='Rascunho',
            valor_total=Decimal('100'),
        )
        resultado = validar_nfe_saida_para_emissao(nf)
        mensagens = ' '.join(resultado.get('mensagens', []))
        self.assertNotIn('entrada fiscal', mensagens.lower())
        self.assertNotIn('nf-e entrada', mensagens.lower())
