"""Fase Saída 3.6 — base PIS/COFINS com dedução opcional de ICMS."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings

from apps.comercial.pricing import percentual_saida_total
from apps.regras_fiscais.base_pis_cofins_saida import (
    calcular_base_pis_cofins_saida,
    percentual_saida_total_com_deducao_icms,
)
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida
from apps.regras_fiscais.saida_fiscal import (
    aplicar_resultado_busca_em_percentuais,
    buscar_regra_fiscal_saida,
    comparar_regra_fiscal_saida_legado_cenario,
)


def _regra_cenario(*, deduz_pis=False, deduz_cofins=False) -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo = CenarioFiscalSaidaEscopo.objects.create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm='84818200',
    )
    return RegraFiscalSaida.objects.create(
        escopo=escopo,
        cenario=cenario,
        ativo=True,
        uf_origem='SP',
        uf_destino='RJ',
        cfop_venda='6102',
        cst_icms='00',
        aliquota_icms=Decimal('18'),
        cst_pis='01',
        aliquota_pis=Decimal('1.65'),
        cst_cofins='01',
        aliquota_cofins=Decimal('7.6'),
        deduzir_icms_base_pis=deduz_pis,
        deduzir_icms_base_cofins=deduz_cofins,
    )


class CalcularBasePisCofinsSaidaTests(TestCase):
    def test_default_sem_deducao(self):
        bp, bc, msgs = calcular_base_pis_cofins_saida(
            Decimal('1000'),
            Decimal('180'),
            deduzir_icms_base_pis=False,
            deduzir_icms_base_cofins=False,
        )
        self.assertEqual(bp, Decimal('1000.00'))
        self.assertEqual(bc, Decimal('1000.00'))
        self.assertEqual(msgs, [])

    def test_deduz_pis(self):
        bp, bc, _ = calcular_base_pis_cofins_saida(
            Decimal('1000'),
            Decimal('180'),
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=False,
        )
        self.assertEqual(bp, Decimal('820.00'))
        self.assertEqual(bc, Decimal('1000.00'))

    def test_deduz_cofins(self):
        bp, bc, _ = calcular_base_pis_cofins_saida(
            Decimal('1000'),
            Decimal('180'),
            deduzir_icms_base_pis=False,
            deduzir_icms_base_cofins=True,
        )
        self.assertEqual(bp, Decimal('1000.00'))
        self.assertEqual(bc, Decimal('820.00'))

    def test_base_nao_negativa(self):
        bp, bc, _ = calcular_base_pis_cofins_saida(
            Decimal('100'),
            Decimal('500'),
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=True,
        )
        self.assertEqual(bp, Decimal('0.00'))
        self.assertEqual(bc, Decimal('0.00'))

    def test_deriva_icms_por_aliquota(self):
        bp, _, msgs = calcular_base_pis_cofins_saida(
            Decimal('1000'),
            None,
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=False,
            aliquota_icms_pct=Decimal('18'),
        )
        self.assertEqual(bp, Decimal('820.00'))
        self.assertEqual(msgs, [])

    def test_icms_indisponivel_mensagem(self):
        _, _, msgs = calcular_base_pis_cofins_saida(
            Decimal('1000'),
            None,
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=False,
        )
        self.assertTrue(msgs)


class PercentualSaidaComDeducaoTests(TestCase):
    def test_legado_ignora_deducao(self):
        sem, _ = percentual_saida_total_com_deducao_icms(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            origem='LEGADO',
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=True,
        )
        esperado = percentual_saida_total(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
        )
        self.assertEqual(sem, esperado)

    def test_cenario_com_deducao_reduz_percentual_efetivo(self):
        sem, _ = percentual_saida_total_com_deducao_icms(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            origem='CENARIO_SAIDA',
            deduzir_icms_base_pis=False,
            deduzir_icms_base_cofins=False,
        )
        com, _ = percentual_saida_total_com_deducao_icms(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            origem='CENARIO_SAIDA',
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=True,
        )
        self.assertGreater(sem, com)


class BuscaECenarioDeducaoTests(TestCase):
    def setUp(self):
        self.regra = _regra_cenario(deduz_pis=True, deduz_cofins=True)
        RegraFiscal.objects.create(
            ncm='84818200',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12,
            aliquota_pis=1.65,
            aliquota_cofins=7.6,
        )

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
    def test_buscar_expoe_campos(self):
        r = buscar_regra_fiscal_saida(ncm='84818200', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')
        self.assertTrue(r['deduzir_icms_base_pis'])
        self.assertTrue(r['deduzir_icms_base_cofins'])

    def test_default_false_nao_altera_percentuais(self):
        cenario = garantir_cenario_saida_padrao()
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818202',
        )
        regra = RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='6102',
            aliquota_icms=Decimal('18'),
            aliquota_pis=Decimal('1.65'),
            aliquota_cofins=Decimal('7.6'),
        )
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True):
            r = buscar_regra_fiscal_saida(ncm='84818202', uf_origem='SP', uf_destino='RJ')
        campos = aplicar_resultado_busca_em_percentuais(r)
        self.assertFalse(campos['deduzir_icms_base_pis'])
        self.assertFalse(campos['deduzir_icms_base_cofins'])
        self.assertEqual(regra.id, r['regra_id'])

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
    def test_comparativo_diverge_deducao(self):
        cmp = comparar_regra_fiscal_saida_legado_cenario(
            ncm='84818200',
            uf_origem='SP',
            uf_destino='RJ',
        )
        self.assertTrue(cmp['cenario']['deduzir_icms_base_pis'])
        self.assertFalse(cmp['legado']['deduzir_icms_base_pis'])
        campos = {d['campo'] for d in cmp['divergencias']}
        self.assertIn('deduzir_icms_base_pis', campos)
        self.assertIn('deduzir_icms_base_cofins', campos)
