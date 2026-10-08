"""Fase 2A — EstoqueBarra a partir da composição validada na conferência."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.fiscal.aplicacao_estoque_barra_conferencia import (
    aplicar_estoque_barras_composicao_conferencia,
    estornar_barras_composicao_item,
    saldo_barras_produto_metros,
    saldo_pecas_produto_kg,
)
from apps.fiscal.aplicacao_estoque_conferencia import aplicar_estoque_fisico_conferencia
from apps.fiscal.composicao_fisica_conferencia import REGRA_KG_PARA_M_PESO_POR_METRO
from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia
from apps.fiscal.models import (
    EstoqueBarra,
    ItemNFeEntradaConferenciaEquivalencia,
)
from apps.fiscal.rastreabilidade_conferencia import sincronizar_equivalencias_entrada_item
from apps.fiscal.tests.test_conferencia_equivalencia_entrada import (
    _criar_composicao_quatro_chapas,
    _setup_chapa_conferencia,
    _setup_tubo_conferencia,
)
from apps.fiscal.tests.test_aplicacao_estoque_conferencia import _setup_conferencia


def _criar_grupo_composicao(linha, ordem: int, qtd_barras: int, comprimento_m: str) -> None:
    comp = Decimal(comprimento_m)
    ItemNFeEntradaConferenciaEquivalencia.objects.create(
        item_conferencia=linha,
        ordem=ordem,
        qtd_barras=qtd_barras,
        comprimento_unitario_m=comp,
        metros=Decimal(qtd_barras) * comp,
    )


def _criar_composicao_tres_barras(linha, comprimentos=('5.800', '6.000', '5.950')) -> None:
    for ordem, comp in enumerate(comprimentos, start=1):
        _criar_grupo_composicao(linha, ordem, 1, comp)


class AplicacaoEstoqueBarraConferenciaTests(TestCase):
    def test_nf_m_tres_barras_cria_tres_estoque_barra(self):
        ctx = _setup_tubo_conferencia('EB1', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        _criar_composicao_tres_barras(linha)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])

        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])

        barras = EstoqueBarra.objects.filter(item_conferencia=linha).order_by('equivalencia_entrada__ordem')
        self.assertEqual(barras.count(), 3)
        self.assertEqual(
            [b.comprimento_original_m for b in barras],
            [Decimal('5.800'), Decimal('6.000'), Decimal('5.950')],
        )
        self.assertTrue(all(b.saldo_m == b.comprimento_original_m for b in barras))
        self.assertTrue(all(b.unidade_base == 'M' for b in barras))
        self.assertTrue(all(b.status == EstoqueBarra.Status.DISPONIVEL for b in barras))
        self.assertTrue(all(b.origem == EstoqueBarra.Origem.CONFERENCIA_NFE_ENTRADA for b in barras))

    def test_soma_saldos_barras_igual_quantidade_estoque_calculada(self):
        ctx = _setup_tubo_conferencia('EB2', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        _criar_composicao_tres_barras(linha)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        linha.refresh_from_db()

        soma_barras = sum(
            EstoqueBarra.objects.filter(item_conferencia=linha).values_list('saldo_m', flat=True),
            Decimal('0'),
        )
        self.assertEqual(soma_barras, linha.quantidade_estoque_calculada)
        self.assertEqual(soma_barras, Decimal('17.750'))
        self.assertEqual(saldo_barras_produto_metros(ctx['prod'].id), Decimal('17.750'))

    def test_aplicacao_duas_vezes_nao_duplica_barras(self):
        ctx = _setup_tubo_conferencia('EB3', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        _criar_composicao_tres_barras(linha)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])

        aplicar_estoque_barras_composicao_conferencia(
            linha,
            fornecedor_id=ctx['forn'].id,
            nfe_entrada_historica_id=ctx['nf'].id,
            nf_numero=ctx['nf'].numero,
            conferencia_id=ctx['conf'].id,
        )
        aplicar_estoque_barras_composicao_conferencia(
            linha,
            fornecedor_id=ctx['forn'].id,
            nfe_entrada_historica_id=ctx['nf'].id,
            nf_numero=ctx['nf'].numero,
            conferencia_id=ctx['conf'].id,
        )
        self.assertEqual(EstoqueBarra.objects.filter(item_conferencia=linha).count(), 3)

    def test_produto_sem_composicao_fisica_nao_cria_estoque_barra(self):
        ctx = _setup_conferencia('EB4', qty='10.000')
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertEqual(EstoqueBarra.objects.filter(produto=ctx['prod']).count(), 0)

    def test_nf_kg_convertida_cria_barras_em_metros(self):
        ctx = _setup_tubo_conferencia(
            'EB5',
            qty='5.768',
            unidade_nf='KG',
            controla_composicao=True,
            peso_por_metro='0.325',
        )
        linha = ctx['linha']
        # 5.768 kg / 0.325 = 17.748 M (arredondado 3 casas)
        _criar_composicao_tres_barras(linha, ('5.800', '6.000', '5.948'))
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)

        barras = EstoqueBarra.objects.filter(item_conferencia=linha)
        self.assertEqual(barras.count(), 3)
        self.assertTrue(all(b.unidade_base == 'M' for b in barras))
        meta = barras.first().metadata.get('conversao_estoque_auditoria') or {}
        self.assertEqual(meta.get('regra_conversao'), REGRA_KG_PARA_M_PESO_POR_METRO)

    def test_alteracao_composicao_antes_aplicacao_nao_duplica_barras(self):
        ctx = _setup_tubo_conferencia('EB6', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        _criar_composicao_tres_barras(linha, ('5.000', '6.000', '6.750'))
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])

        aplicar_estoque_barras_composicao_conferencia(
            linha,
            fornecedor_id=ctx['forn'].id,
            nfe_entrada_historica_id=ctx['nf'].id,
        )
        self.assertEqual(EstoqueBarra.objects.filter(item_conferencia=linha).count(), 3)

        sincronizar_equivalencias_entrada_item(
            linha,
            [
                {'ordem': 1, 'qtd_barras': 1, 'comprimento_unitario_m': '5.800'},
                {'ordem': 2, 'qtd_barras': 1, 'comprimento_unitario_m': '6.000'},
                {'ordem': 3, 'qtd_barras': 1, 'comprimento_unitario_m': '5.950'},
            ],
        )
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])

        aplicar_estoque_barras_composicao_conferencia(
            linha,
            fornecedor_id=ctx['forn'].id,
            nfe_entrada_historica_id=ctx['nf'].id,
        )
        barras = EstoqueBarra.objects.filter(item_conferencia=linha).exclude(
            status=EstoqueBarra.Status.CANCELADA,
        )
        self.assertEqual(barras.count(), 3)
        self.assertEqual(
            sorted(b.comprimento_original_m for b in barras),
            [Decimal('5.800'), Decimal('5.950'), Decimal('6.000')],
        )

    def test_estorno_cancela_barras_sem_consumo(self):
        ctx = _setup_tubo_conferencia('EB7', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        _criar_composicao_tres_barras(linha)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)

        canceladas = estornar_barras_composicao_item(linha)
        self.assertEqual(canceladas, 3)
        self.assertEqual(
            EstoqueBarra.objects.filter(
                item_conferencia=linha,
                status=EstoqueBarra.Status.CANCELADA,
            ).count(),
            3,
        )
        self.assertEqual(saldo_barras_produto_metros(ctx['prod'].id), Decimal('0'))

    def test_grupo_dez_barras_cria_dez_estoque_barra(self):
        ctx = _setup_tubo_conferencia('EB8', qty='60.000', controla_composicao=True)
        linha = ctx['linha']
        _criar_grupo_composicao(linha, 1, 10, '6.000')
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        barras = EstoqueBarra.objects.filter(item_conferencia=linha)
        self.assertEqual(barras.count(), 10)
        self.assertTrue(all(b.saldo_m == Decimal('6.000') for b in barras))

    def test_uma_barra_de_seis_metros(self):
        ctx = _setup_tubo_conferencia('EB9', qty='6.000', controla_composicao=True)
        linha = ctx['linha']
        _criar_grupo_composicao(linha, 1, 1, '6.000')
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        barra = EstoqueBarra.objects.get(item_conferencia=linha)
        self.assertEqual(barra.saldo_m, Decimal('6.000'))
        self.assertEqual(barra.comprimento_original_m, Decimal('6.000'))

    def test_migration_estoque_barra_existe(self):
        from django.apps import apps

        model = apps.get_model('fiscal', 'EstoqueBarra')
        self.assertIsNotNone(model._meta.get_field('sequencia_grupo'))
        self.assertIsNotNone(model._meta.get_field('saldo'))
        self.assertIsNotNone(model._meta.get_field('tipo_composicao'))


class AplicacaoEstoquePecaKgConferenciaTests(TestCase):
    """Critério de aceite: 4 chapas com pesos diferentes → 4 EstoqueBarra em KG."""

    def test_quatro_chapas_cria_quatro_estoque_barra_kg(self):
        ctx = _setup_chapa_conferencia('PKA1', qty='486.300')
        linha = ctx['linha']
        pesos = ('121.800', '119.450', '122.600', '122.450')
        _criar_composicao_quatro_chapas(linha, pesos)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])

        pecas = EstoqueBarra.objects.filter(item_conferencia=linha).order_by('equivalencia_entrada__ordem')
        self.assertEqual(pecas.count(), 4)
        self.assertEqual(
            [p.saldo for p in pecas],
            [Decimal(p) for p in pesos],
        )
        self.assertTrue(all(p.unidade_base == 'KG' for p in pecas))
        self.assertTrue(all(p.tipo_composicao == EstoqueBarra.TipoComposicao.PECA_KG for p in pecas))
        self.assertTrue(all(p.saldo == p.quantidade_original for p in pecas))
        self.assertIsNone(pecas.first().saldo_m)
        self.assertEqual(saldo_pecas_produto_kg(ctx['prod'].id), Decimal('486.300'))

    def test_aplicacao_idempotente_pecas_kg(self):
        ctx = _setup_chapa_conferencia('PKA2', qty='486.300')
        linha = ctx['linha']
        _criar_composicao_quatro_chapas(linha)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        for _ in range(2):
            aplicar_estoque_barras_composicao_conferencia(
                linha,
                fornecedor_id=ctx['forn'].id,
                nfe_entrada_historica_id=ctx['nf'].id,
            )
        self.assertEqual(EstoqueBarra.objects.filter(item_conferencia=linha).count(), 4)
