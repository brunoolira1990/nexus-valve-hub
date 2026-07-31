"""Fase 1 — conciliação operacional NF-e Entrada (histórica) × Pedido de Venda."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import (
    FaturamentoPedidoVenda,
    ItemFaturamentoPedidoVenda,
    ItemPedidoCompra,
    ItemPedidoVenda,
    PedidoCompra,
    PedidoVenda,
)
from apps.comercial.services.alocacao_entrada_venda_service import (
    ESTADO_CONCILIADO,
    ESTADO_DIVERGENTE,
    ESTADO_PARCIAL,
    ESTADO_SEM_ALOCACAO,
    TOL,
    alocar_entrada_para_venda,
    desvincular_alocacao_entrada_venda,
    estado_operacional_entrada,
    montar_resumo_entrada_venda,
    total_alocado_destino_pv,
    total_alocado_entrada,
)
from apps.comercial.services.atendimentos_operacionais_service import (
    calcular_kpis_atendimentos_operacionais,
)
from apps.fiscal.modelo_operacional import (
    StatusEntradaFiscal,
    TipoAtendimentoItem,
    resolver_origem_destino_por_tipo,
)
from apps.fiscal.models import (
    AlocacaoAtendimento,
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaida,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaida,
)
from apps.financeiro.models import TituloFinanceiro
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(suffix: str) -> Produto:
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FE{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Prod {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PE-{suffix}',
        unidade='PC',
        ncm='84818099',
    )


class AlocacaoEntradaVendaFase1Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('aloc_ev', 'ev@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('EV1')
        self.cliente = Cliente.objects.create(razao_social='Cliente EV', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn EV', cnpj=_cnpj(), uf='SP')

        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'EV1' + 'Z' * 40)[:44],
            numero='NE-EV1',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.fornecedor,
            cstat='100',
            tp_amb='1',
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': '10.000', 'uCom': 'PC'},
        )
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.CONFERIDA,
        )
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)
        self.linha.produto = self.produto
        self.linha.quantidade_nf = Decimal('10')
        self.linha.unidade_nf = 'PC'
        self.linha.quantidade_estoque_calculada = Decimal('10.000')
        self.linha.unidade_estoque_calculada = 'PC'
        self.linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        self.linha.save()

        self.pv = PedidoVenda.objects.create(
            numero='PV-EV1',
            cliente=self.cliente,
            data=date(2026, 7, 1),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('50'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('10'),
        )

    def test_alocacao_parcial_valida_sem_efeitos_colaterais(self):
        estoque_antes = EstoqueCorrida.objects.count()
        titulos_antes = TituloFinanceiro.objects.count()
        qtd_rec_pc = None
        pc = PedidoCompra.objects.create(
            numero='PC-EV1',
            fornecedor=self.fornecedor,
            data=date(2026, 7, 1),
        )
        ipc = ItemPedidoCompra.objects.create(
            pedido=pc,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('40'),
        )
        self.linha.item_pedido_compra = ipc
        self.linha.save(update_fields=['item_pedido_compra'])
        ipc.refresh_from_db()
        qtd_rec_pc = ipc.quantidade_recebida

        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '4.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data['acao'], 'criado')
        self.assertEqual(r.data['alocacao']['quantidade_necessaria'], '4.000')
        self.assertEqual(r.data['resumo']['estado_operacional'], ESTADO_PARCIAL)
        self.assertEqual(r.data['resumo']['total_alocado'], '4.000')
        self.assertEqual(r.data['resumo']['saldo_entrada'], '6.000')

        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.assertEqual(TituloFinanceiro.objects.count(), titulos_antes)
        ipc.refresh_from_db()
        self.assertEqual(ipc.quantidade_recebida, qtd_rec_pc)
        self.linha.refresh_from_db()
        self.assertIsNone(self.linha.estoque_aplicado_em)

    def test_uma_entrada_varios_itens_venda(self):
        pv2 = PedidoVenda.objects.create(numero='PV-EV2', cliente=self.cliente, data=date(2026, 7, 2))
        item_pv2 = ItemPedidoVenda.objects.create(
            pedido=pv2,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('50'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('5'),
        )
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=item_pv2.pk,
            quantidade=Decimal('3'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        resumo = montar_resumo_entrada_venda(self.linha)
        self.assertEqual(resumo['total_alocado'], '7.000')
        self.assertEqual(resumo['estado_operacional'], ESTADO_PARCIAL)
        self.assertEqual(len(resumo['alocacoes']), 2)

    def test_varias_entradas_um_item_venda(self):
        item_nf2 = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=2,
            prod_json={'qCom': '5'},
        )
        linha2, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf2)
        linha2.produto = self.produto
        linha2.quantidade_estoque_calculada = Decimal('5.000')
        linha2.unidade_estoque_calculada = 'PC'
        linha2.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        linha2.save()

        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('6'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        alocar_entrada_para_venda(
            item_conferencia_id=linha2.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('3'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        total = AlocacaoAtendimento.objects.filter(pedido_venda_item=self.item_pv).count()
        self.assertEqual(total, 2)

    def test_excesso_origem_rejeitado(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '11.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)

    def test_excesso_destino_rejeitado(self):
        self.item_pv.quantidade = Decimal('3')
        self.item_pv.quantidade_estoque_calculada = Decimal('3')
        self.item_pv.save(update_fields=['quantidade', 'quantidade_estoque_calculada'])
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '4.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)

    def test_quantidade_zero_ou_negativa(self):
        for q in ('0', '-1', '0.000'):
            r = self.client.post(
                '/api/alocacoes-atendimento/alocar-entrada-venda/',
                {
                    'item_conferencia_id': self.linha.pk,
                    'pedido_venda_item_id': self.item_pv.pk,
                    'quantidade': q,
                },
                format='json',
            )
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, q)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)

    def test_edicao_recalcula_saldos(self):
        cri, acao = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao, 'criado')
        r = self.client.patch(
            f'/api/alocacoes-atendimento/{cri.pk}/quantidade-entrada-venda/',
            {'quantidade': '7.000'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['resumo']['total_alocado'], '7.000')
        self.assertEqual(r.data['resumo']['saldo_entrada'], '3.000')

    def test_desvinculacao_restaura_saldos(self):
        cri, _ = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(montar_resumo_entrada_venda(self.linha)['estado_operacional'], ESTADO_CONCILIADO)
        r = self.client.post(f'/api/alocacoes-atendimento/{cri.pk}/desvincular-entrada-venda/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)
        self.assertEqual(r.data['resumo']['estado_operacional'], ESTADO_SEM_ALOCACAO)
        self.assertEqual(r.data['resumo']['saldo_entrada'], '10.000')
        self.linha.refresh_from_db()
        self.assertIsNone(self.linha.estoque_aplicado_em)

    def test_cadeia_comercial_incompativel(self):
        pv_outro = PedidoVenda.objects.create(numero='PV-OUT', cliente=self.cliente, data=date(2026, 7, 3))
        item_outro = ItemPedidoVenda.objects.create(
            pedido=pv_outro,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('10'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('5'),
        )
        fat = FaturamentoPedidoVenda.objects.create(
            pedido=pv_outro,
            numero_faturamento='FAT-OUT',
        )
        fat_item = ItemFaturamentoPedidoVenda.objects.create(
            faturamento=fat,
            item_pedido=item_outro,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('10'),
            valor_total=Decimal('50'),
        )
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '1.000',
                'faturamento_item_id': fat_item.pk,
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cadeia', (r.data.get('detail') or '').lower())

    def test_deriva_faturamento_e_nfe_saida(self):
        fat = FaturamentoPedidoVenda.objects.create(
            pedido=self.pv,
            numero_faturamento='FAT-EV1',
        )
        fat_item = ItemFaturamentoPedidoVenda.objects.create(
            faturamento=fat,
            item_pedido=self.item_pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('50'),
            valor_total=Decimal('500'),
        )
        nf = NFeSaida.objects.create(
            numero='NF-EV1',
            cliente=self.cliente,
            pedido_venda=self.pv,
            faturamento_pedido_venda=fat,
            data=date(2026, 7, 1),
            status='Rascunho',
            valor_total=Decimal('500'),
        )
        nf_item = ItemNFeSaida.objects.create(
            nf=nf,
            item_faturamento_pedido=fat_item,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor=Decimal('50'),
        )
        aloc, acao = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('2'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao, 'criado')
        self.assertEqual(aloc.faturamento_item_id, fat_item.pk)
        self.assertEqual(aloc.item_nf_saida_id, nf_item.pk)
        self.assertEqual(aloc.status_entrada_fiscal, 'PENDENTE')

    def test_multiplos_faturamentos_nao_persiste_fk_ambigua(self):
        fat1 = FaturamentoPedidoVenda.objects.create(pedido=self.pv, numero_faturamento='FAT-A')
        fat2 = FaturamentoPedidoVenda.objects.create(pedido=self.pv, numero_faturamento='FAT-B')
        ItemFaturamentoPedidoVenda.objects.create(
            faturamento=fat1,
            item_pedido=self.item_pv,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('50'),
            valor_total=Decimal('250'),
        )
        ItemFaturamentoPedidoVenda.objects.create(
            faturamento=fat2,
            item_pedido=self.item_pv,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('50'),
            valor_total=Decimal('250'),
        )
        aloc, _ = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('2'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertIsNone(aloc.faturamento_item_id)
        self.assertIsNone(aloc.item_nf_saida_id)
        opcao = self.client.get(
            '/api/alocacoes-atendimento/opcoes/pedidos-venda-itens/',
            {'search': 'PV-EV1'},
        )
        self.assertEqual(opcao.status_code, status.HTTP_200_OK)
        row = next(x for x in opcao.data if x['id'] == self.item_pv.pk)
        self.assertTrue(row['documentos_relacionados']['cadeia_ambigua'])
        self.assertEqual(len(row['documentos_relacionados']['faturamentos']), 2)

    def test_upsert_mesma_combinacao_substitui_nao_soma(self):
        a1, acao1 = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('2'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        a2, acao2 = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('5'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao1, 'criado')
        self.assertEqual(acao2, 'atualizado')
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 1)
        self.assertEqual(a2.quantidade_necessaria, Decimal('5'))
        self.assertEqual(montar_resumo_entrada_venda(self.linha)['total_alocado'], '5.000')
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '3.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['acao'], 'atualizado')
        self.assertEqual(r.data['resumo']['total_alocado'], '3.000')

    def test_crud_generico_nao_contorna_limites(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            {
                'pedido_venda_item_id': self.item_pv.pk,
                'produto_id': self.produto.pk,
                'nf_entrada_historica_item_id': self.item_nf.pk,
                'quantidade_necessaria': '11.000',
                'quantidade_atendida': '11.000',
                'quantidade_pendente': '0',
                'tipo_atendimento': 'ENTRADA_CONCILIADA',
                'status_entrada_fiscal': 'PENDENTE',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)

    def test_crud_generico_entrada_pv_usa_dominio(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            {
                'pedido_venda_item_id': self.item_pv.pk,
                'produto_id': self.produto.pk,
                'nf_entrada_historica_item_id': self.item_nf.pk,
                'quantidade_necessaria': '3.000',
                'quantidade_atendida': '3.000',
                'quantidade_pendente': '0',
                'tipo_atendimento': 'ENTRADA_CONCILIADA',
                'status_entrada_fiscal': 'PENDENTE',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 1)
        r2 = self.client.post(
            '/api/alocacoes-atendimento/',
            {
                'pedido_venda_item_id': self.item_pv.pk,
                'produto_id': self.produto.pk,
                'nf_entrada_historica_item_id': self.item_nf.pk,
                'quantidade_necessaria': '4.000',
                'quantidade_atendida': '4.000',
                'quantidade_pendente': '0',
                'tipo_atendimento': 'ENTRADA_CONCILIADA',
                'status_entrada_fiscal': 'PENDENTE',
            },
            format='json',
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.data)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 1)
        self.assertEqual(Decimal(r2.data['quantidade_necessaria']), Decimal('4'))

    def test_estoque_nao_aplicado_permite_com_aviso(self):
        self.assertIsNone(self.linha.estoque_aplicado_em)
        r = self.client.get(
            '/api/alocacoes-atendimento/resumo-entrada-venda/',
            {'item_conferencia_id': self.linha.pk},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['estoque_aplicado'])
        self.assertIn('não foi aplicado', r.data['aviso_estoque'])
        self.assertNotEqual(r.data['estado_operacional'], 'DIVERGENTE')
        aloc, _ = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('1'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertIsNotNone(aloc.pk)
        self.assertEqual(EstoqueCorrida.objects.count(), 0)

    def test_quantidade_interna_zerada_bloqueia(self):
        self.linha.quantidade_estoque_calculada = Decimal('0')
        self.linha.save(update_fields=['quantidade_estoque_calculada'])
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '1.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantidade_estoque_calculada', (r.data.get('detail') or '').lower())

    def test_unidade_incompativel_bloqueia(self):
        self.item_pv.unidade_estoque_calculada = 'KG'
        self.item_pv.quantidade_estoque_calculada = Decimal('10')
        self.item_pv.save(update_fields=['unidade_estoque_calculada', 'quantidade_estoque_calculada'])
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '1.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unidades incompatíveis', (r.data.get('detail') or '').lower())


class ContratoCanonicoS4BACaracterizacaoTests(TestCase):
    """S4B-A — caracteriza o contrato ATUAL (inclui inconsistências conhecidas).

    Não corrige comportamento: documenta tipo × status × estado quantitativo.
    """

    def setUp(self):
        self.produto = _produto('S4BA')
        self.cliente = Cliente.objects.create(razao_social='Cliente S4BA', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn S4BA', cnpj=_cnpj(), uf='SP')
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'S4B' + 'Z' * 40)[:44],
            numero='NE-S4BA',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.fornecedor,
            cstat='100',
            tp_amb='1',
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'qCom': '10.000', 'uCom': 'PC'},
        )
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.CONFERIDA,
        )
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)
        self.linha.produto = self.produto
        self.linha.quantidade_nf = Decimal('10')
        self.linha.unidade_nf = 'PC'
        self.linha.quantidade_estoque_calculada = Decimal('10.000')
        self.linha.unidade_estoque_calculada = 'PC'
        self.linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        self.linha.save()
        self.pv = PedidoVenda.objects.create(numero='PV-S4BA', cliente=self.cliente, data=date(2026, 7, 1))
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('50'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('10'),
        )

    def test_s4ba_fase1_grava_tipo_conciliada_e_status_pendente(self):
        """INCONSISTÊNCIA CARACTERIZADA (atual):

        - Helper ``resolver_origem_destino_por_tipo(ENTRADA_CONCILIADA)`` sugere status CONCILIADA.
        - Fase 1 ``_montar_dados_alocacao`` grava status PENDENTE explicitamente.
        - ``ENTRADA_CONCILIADA`` funciona como *tipo/origem do atendimento* (opção A),
          não como conclusão integral (opção B).
        """
        _, _, status_sugerido = resolver_origem_destino_por_tipo(TipoAtendimentoItem.ENTRADA_CONCILIADA)
        self.assertEqual(status_sugerido, StatusEntradaFiscal.CONCILIADA)

        aloc, acao = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao, 'criado')
        self.assertEqual(aloc.tipo_atendimento, TipoAtendimentoItem.ENTRADA_CONCILIADA)
        self.assertEqual(aloc.status_entrada_fiscal, StatusEntradaFiscal.PENDENTE)
        self.assertEqual(
            montar_resumo_entrada_venda(self.linha)['estado_operacional'],
            ESTADO_CONCILIADO,
        )

    def test_s4ba_kpi_entradas_conciliadas_usa_status_persistido_nao_estado_qty(self):
        """KPI atual conta ``status_entrada_fiscal=CONCILIADA``, não estado quantitativo."""
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(montar_resumo_entrada_venda(self.linha)['estado_operacional'], ESTADO_CONCILIADO)
        kpis = calcular_kpis_atendimentos_operacionais()
        # Alocação Fase 1 integral → estado CONCILIADO, mas status PENDENTE → fora do KPI.
        self.assertEqual(kpis['entradas_conciliadas'], 0)
        self.assertGreaterEqual(kpis['entradas_pendentes'], 1)

    def test_s4ba_estado_operacional_regra_quantitativa_canonica(self):
        self.assertEqual(
            estado_operacional_entrada(quantidade_disponivel=Decimal('10'), total_alocado=Decimal('0')),
            ESTADO_SEM_ALOCACAO,
        )
        self.assertEqual(
            estado_operacional_entrada(quantidade_disponivel=Decimal('10'), total_alocado=Decimal('4')),
            ESTADO_PARCIAL,
        )
        self.assertEqual(
            estado_operacional_entrada(quantidade_disponivel=Decimal('10'), total_alocado=Decimal('10')),
            ESTADO_CONCILIADO,
        )
        self.assertEqual(
            estado_operacional_entrada(
                quantidade_disponivel=Decimal('10'),
                total_alocado=Decimal('10') - TOL,
            ),
            ESTADO_CONCILIADO,
        )
        self.assertEqual(
            estado_operacional_entrada(quantidade_disponivel=Decimal('10'), total_alocado=Decimal('10.001')),
            ESTADO_DIVERGENTE,
        )

    def test_s4ba_total_alocado_soma_quantidade_necessaria_por_origem(self):
        pv2 = PedidoVenda.objects.create(numero='PV-S4BA-2', cliente=self.cliente, data=date(2026, 7, 2))
        item_pv2 = ItemPedidoVenda.objects.create(
            pedido=pv2,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('50'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('5'),
        )
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=item_pv2.pk,
            quantidade=Decimal('3'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(total_alocado_entrada(self.item_nf.pk), Decimal('7'))
        self.assertEqual(total_alocado_destino_pv(self.item_pv.pk), Decimal('4'))
        self.assertEqual(montar_resumo_entrada_venda(self.linha)['estado_operacional'], ESTADO_PARCIAL)

    def test_s4ba_n_entradas_um_destino_agrega_no_pv(self):
        item_nf2 = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=2,
            prod_json={'qCom': '5'},
        )
        linha2, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf2)
        linha2.produto = self.produto
        linha2.quantidade_estoque_calculada = Decimal('5.000')
        linha2.unidade_estoque_calculada = 'PC'
        linha2.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        linha2.save()

        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('6'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        alocar_entrada_para_venda(
            item_conferencia_id=linha2.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(total_alocado_destino_pv(self.item_pv.pk), Decimal('10'))
        self.assertEqual(total_alocado_entrada(self.item_nf.pk), Decimal('6'))
        self.assertEqual(total_alocado_entrada(item_nf2.pk), Decimal('4'))

    def test_s4ba_upsert_substitui_nao_soma_e_ajuste_para_baixo(self):
        a1, acao1 = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('7'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao1, 'criado')
        a2, acao2 = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('7'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao2, 'atualizado')
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(AlocacaoAtendimento.objects.count(), 1)
        self.assertEqual(a2.quantidade_necessaria, Decimal('7.000'))

        a3, acao3 = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('3'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(acao3, 'atualizado')
        self.assertEqual(a3.quantidade_necessaria, Decimal('3.000'))
        self.assertEqual(a3.quantidade_atendida, Decimal('3.000'))
        self.assertEqual(a3.quantidade_pendente, Decimal('0'))
        self.assertEqual(total_alocado_entrada(self.item_nf.pk), Decimal('3'))

    def test_s4ba_desvincular_remove_registro_e_agregado_zera(self):
        aloc, _ = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('5'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        desvincular_alocacao_entrada_venda(aloc,
            origem_sistema='SISTEMA:DESVINCULAR_ENTRADA_VENDA')
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)
        self.assertEqual(total_alocado_entrada(self.item_nf.pk), Decimal('0'))
        self.assertEqual(
            montar_resumo_entrada_venda(self.linha)['estado_operacional'],
            ESTADO_SEM_ALOCACAO,
        )

    def test_s4ba_homologacao_bloqueada_na_validacao_de_vinculo(self):
        from apps.comercial.services.alocacao_atendimento_service import AlocacaoAtendimentoErro
        from apps.comercial.services.alocacao_atendimento_vinculos import validar_vinculos_alocacao

        self.nf.tp_amb = '2'
        self.nf.save(update_fields=['tp_amb'])
        with self.assertRaises(AlocacaoAtendimentoErro) as ctx:
            validar_vinculos_alocacao({'nf_entrada_historica_item': self.item_nf})
        self.assertIn('homologação', str(ctx.exception).lower())

    def test_s4ba_fase1_nao_movimenta_estoque_nem_financeiro(self):
        estoque_antes = EstoqueCorrida.objects.count()
        titulos_antes = TituloFinanceiro.objects.count()
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('2'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.assertEqual(TituloFinanceiro.objects.count(), titulos_antes)
