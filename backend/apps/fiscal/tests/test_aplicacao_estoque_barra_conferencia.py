"""Fase 2A — EstoqueBarra a partir da composição validada na conferência."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.fiscal.aplicacao_estoque_barra_conferencia import (
    aplicar_estoque_barras_composicao_conferencia,
    estornar_barras_composicao_item,
    saldo_barras_produto_metros,
)
from apps.fiscal.aplicacao_estoque_conferencia import aplicar_estoque_fisico_conferencia
from apps.fiscal.composicao_fisica_conferencia import REGRA_KG_PARA_M_PESO_POR_METRO
from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia
from apps.fiscal.models import (
    EstoqueBarra,
    ItemNFeEntradaConferenciaEquivalencia,
)
from apps.fiscal.rastreabilidade_conferencia import sincronizar_equivalencias_entrada_item
from apps.fiscal.tests.test_conferencia_equivalencia_entrada import _setup_tubo_conferencia
from apps.fiscal.tests.test_aplicacao_estoque_conferencia import _setup_conferencia


def _criar_composicao_tres_barras(linha, metros=('5.800', '6.000', '5.950')) -> None:
    for ordem, m in enumerate(metros, start=1):
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha,
            ordem=ordem,
            metros=Decimal(m),
        )


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
                {'ordem': 1, 'metros': '5.800'},
                {'ordem': 2, 'metros': '6.000'},
                {'ordem': 3, 'metros': '5.950'},
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

    def test_migration_estoque_barra_existe(self):
        from django.apps import apps

        model = apps.get_model('fiscal', 'EstoqueBarra')
        self.assertIsNotNone(model._meta.get_field('equivalencia_entrada'))
        self.assertIsNotNone(model._meta.get_field('codigo_interno_barra'))
