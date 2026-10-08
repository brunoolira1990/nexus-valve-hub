"""ERP 4.0.11 — visibilidade operacional de atendimento (resumo read-only)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.faturamento_pedido_venda import montar_resumo_faturamento
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.serializers import PedidoVendaSerializer
from apps.comercial.services.resumo_atendimento_operacional import (
    obter_resumo_atendimento_operacional,
)
from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)
from apps.fiscal.models import AlocacaoAtendimento, EstoqueCorrida, NFeSaida
from apps.fiscal.serializers import NFeSaidaSerializer
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


class ResumoAtendimentoOperacionalTests(TestCase):
    def setUp(self):
        self.produto = _produto('4011')
        self.cliente = Cliente.objects.create(
            razao_social='Cliente 4011',
            cnpj='11.111.111/0001-11',
        )
        self.pv = PedidoVenda.objects.create(
            numero='PV-4011',
            cliente=self.cliente,
            data=date(2026, 5, 23),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('100'),
        )

    def test_resumo_sem_alocacao_retorna_tem_alocacao_false(self):
        res = obter_resumo_atendimento_operacional(self.pv)
        self.assertFalse(res['tem_alocacao'])
        self.assertEqual(res['badges'][0]['status'], 'nao_definido')

    def test_resumo_entrada_pendente_badge(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('5'),
            quantidade_pendente=Decimal('5'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
            origem_fisica=OrigemFisica.FORNECEDOR,
            destino_fisico=DestinoFisico.CLIENTE,
        )
        res = obter_resumo_atendimento_operacional(self.pv)
        statuses = {b['status'] for b in res['badges']}
        self.assertIn('entrada_pendente', statuses)
        self.assertTrue(res['possui_entrada_pendente'])

    def test_resumo_entrada_conciliada_badge(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('5'),
            quantidade_atendida=Decimal('5'),
            tipo_atendimento=TipoAtendimentoItem.ENTRADA_CONCILIADA,
            status_entrada_fiscal=StatusEntradaFiscal.CONCILIADA,
            origem_fisica=OrigemFisica.ESTOQUE_PROPRIO,
            destino_fisico=DestinoFisico.CLIENTE,
        )
        res = obter_resumo_atendimento_operacional(self.pv)
        statuses = {b['status'] for b in res['badges']}
        self.assertIn('entrada_conciliada', statuses)
        self.assertTrue(res['possui_entrada_conciliada'])

    def test_resumo_retirada_fornecedor_badge(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('3'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
            origem_fisica=OrigemFisica.FORNECEDOR,
            destino_fisico=DestinoFisico.CLIENTE,
        )
        res = obter_resumo_atendimento_operacional(self.pv)
        statuses = {b['status'] for b in res['badges']}
        self.assertIn('retirada_fornecedor', statuses)
        self.assertTrue(res['possui_retirada_fornecedor'])

    def test_resumo_entrega_direta_badge(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('2'),
            tipo_atendimento=TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
            origem_fisica=OrigemFisica.FORNECEDOR,
            destino_fisico=DestinoFisico.CLIENTE,
        )
        res = obter_resumo_atendimento_operacional(self.pv)
        statuses = {b['status'] for b in res['badges']}
        self.assertIn('entrega_direta', statuses)
        self.assertTrue(res['possui_entrega_direta'])

    def test_resumo_atendimento_misto(self):
        item2 = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('2'),
            valor_unitario=Decimal('50'),
        )
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('3'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=item2,
            produto=self.produto,
            quantidade_necessaria=Decimal('2'),
            tipo_atendimento=TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        res = obter_resumo_atendimento_operacional(self.pv)
        self.assertTrue(res['atendimento_misto'])
        statuses = {b['status'] for b in res['badges']}
        self.assertIn('atendimento_misto', statuses)

    def test_pedido_venda_serializer_expoe_resumo_read_only(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        data = PedidoVendaSerializer(self.pv).data
        self.assertIn('resumo_atendimento_operacional', data)
        self.assertTrue(data['resumo_atendimento_operacional']['tem_alocacao'])

    def test_pedido_venda_listagem_omite_resumo(self):
        data = PedidoVendaSerializer(self.pv, context={'omit_resumo_operacional': True}).data
        self.assertIsNone(data['resumo_atendimento_operacional'])

    def test_pedido_venda_listagem_expoe_resumo_enxuto(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        data = PedidoVendaSerializer(self.pv, context={'listagem': True}).data
        resumo = data['resumo_atendimento_operacional']
        self.assertTrue(resumo['tem_alocacao'])
        self.assertIn('badges', resumo)
        self.assertIn('entrada_pendente', {b['status'] for b in resumo['badges']})

    def test_listagem_pv_sem_alocacao_mostra_nao_definido(self):
        data = PedidoVendaSerializer(self.pv, context={'listagem': True}).data
        resumo = data['resumo_atendimento_operacional']
        self.assertFalse(resumo['tem_alocacao'])
        self.assertEqual(resumo['badges'][0]['status'], 'nao_definido')

    def test_resumo_expoe_campos_api_4011(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
            origem_fisica=OrigemFisica.FORNECEDOR,
            destino_fisico=DestinoFisico.CLIENTE,
        )
        from apps.comercial.services.resumo_atendimento_operacional import (
            obter_resumo_atendimento_pv,
        )

        res = obter_resumo_atendimento_pv(self.pv)
        self.assertIn('tipo_atendimento', res)
        self.assertIn('alertas', res)
        self.assertIn('tem_compra_vinculada', res)
        self.assertFalse(res['tem_compra_vinculada'])
        self.assertTrue(len(res['alertas']) >= 1)

    def test_nfe_saida_contexto_nfe_saida_mensagem(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        from apps.comercial.services.resumo_atendimento_operacional import (
            obter_resumo_atendimento_nfe_saida,
        )

        nf = NFeSaida.objects.create(
            numero='NF-CTX',
            cliente=self.cliente,
            pedido_venda=self.pv,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('10'),
        )
        res = obter_resumo_atendimento_nfe_saida(nf)
        self.assertIn('retirada', res['mensagem'].lower())

    def test_nfe_saida_serializer_expoe_resumo_read_only(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
        )
        nf = NFeSaida.objects.create(
            numero='NF-4011',
            cliente=self.cliente,
            pedido_venda=self.pv,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('100'),
        )
        data = NFeSaidaSerializer(nf).data
        self.assertIn('resumo_atendimento_operacional', data)
        self.assertTrue(data['resumo_atendimento_operacional']['tem_alocacao'])

    def test_resumo_nao_altera_estoque(self):
        estoque_antes = EstoqueCorrida.objects.count()
        obter_resumo_atendimento_operacional(self.pv)
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)

    def test_resumo_nao_altera_nfe(self):
        nf = NFeSaida.objects.create(
            numero='NF-4011B',
            cliente=self.cliente,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('50'),
        )
        status_antes = nf.status
        obter_resumo_atendimento_operacional(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, status_antes)

    def test_montar_resumo_faturamento_inclui_resumo_operacional(self):
        resumo = montar_resumo_faturamento(self.pv)
        self.assertIn('resumo_atendimento_operacional', resumo)
        self.assertFalse(resumo['resumo_atendimento_operacional']['tem_alocacao'])

    def test_listagem_nfe_retorna_resumo_enxuto_sem_alocacao_none(self):
        nf = NFeSaida.objects.create(
            numero='NF-4011C',
            cliente=self.cliente,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('10'),
        )
        data = NFeSaidaSerializer(nf, context={'listagem': True}).data
        self.assertIsNone(data['resumo_atendimento_operacional'])

    def test_listagem_nao_retorna_alocacoes_completas(self):
        AlocacaoAtendimento.objects.create(
            pedido_venda_item=self.item_pv,
            produto=self.produto,
            quantidade_necessaria=Decimal('1'),
            tipo_atendimento=TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            status_entrada_fiscal=StatusEntradaFiscal.PENDENTE,
            fornecedor=Fornecedor.objects.create(
                razao_social='Forn 4011',
                cnpj='22.222.222/0001-22',
            ),
        )
        nf = NFeSaida.objects.create(
            numero='NF-4011D',
            cliente=self.cliente,
            pedido_venda=self.pv,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('10'),
        )
        data = NFeSaidaSerializer(nf, context={'listagem': True}).data
        resumo = data['resumo_atendimento_operacional']
        self.assertTrue(resumo['tem_alocacao'])
        self.assertEqual(
            set(resumo.keys()),
            {'tem_alocacao', 'badges', 'mensagem', 'tipo_atendimento', 'status_entrada_fiscal'},
        )
        self.assertNotIn('tipo_principal', resumo)
        self.assertNotIn('origem_fisica_principal', resumo)
        self.assertNotIn('fornecedor_id', resumo)
        self.assertNotIn('Forn 4011', resumo.get('mensagem', ''))
