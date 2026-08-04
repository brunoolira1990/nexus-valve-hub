"""Venda à vista: cobranca/CR sem acoplar meio de pagamento (tPag) a dias_parcelas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.comercial.payment_terms import pagamento_integralmente_a_vista
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao import xml_serializacao as xml_ser
from apps.fiscal.nfe_emissao.xml_serializacao import build_cobr_bindings, build_pag_bindings
from apps.fiscal.nfe_saida_condicao_pagamento import (
    nfe_deve_gerar_cobranca_a_prazo,
    nfe_venda_integralmente_a_vista,
    resolver_dias_parcelas_nfe,
)
from apps.fiscal.nfe_saida_duplicatas import gerar_duplicatas_nfe_saida
from apps.fiscal.nfe_saida_financeiro import (
    MSG_VENDA_A_VISTA,
    gerar_contas_receber_automatico_apos_autorizacao_producao,
    gerar_contas_receber_de_nfe_autorizada,
    montar_flags_financeiro_nfe,
    montar_parcelas_sugeridas_nfe,
    preview_contas_receber_de_nfe,
)
from apps.fiscal.tests.test_nfe_saida_40143_gerar_contas_receber import _autorizar_nf, _autorizar_nf_homologacao
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf


def _marcar_plano(nf: NFeSaida, dias: list[int], texto: str = '') -> NFeSaida:
    nf.dias_parcelas = list(dias)
    nf.quantidade_parcelas = len(dias)
    nf.condicao_pagamento_texto = texto or ('/'.join(str(d) for d in dias) if dias else '')
    nf.titulos_receber = []
    nf.vencimentos_finais = []
    nf.save(
        update_fields=[
            'dias_parcelas',
            'quantidade_parcelas',
            'condicao_pagamento_texto',
            'titulos_receber',
            'vencimentos_finais',
        ],
    )
    return nf


class _FakeDetPag:
    def __init__(self, tPag, vPag):
        self.tPag = tPag
        self.vPag = vPag


class _FakePag:
    def __init__(self, detPag):
        self.detPag = detPag


class _FakeFat:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeDup:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeCobr:
    def __init__(self, fat, dup):
        self.fat = fat
        self.dup = dup


class _FakeInf:
    class Pag:
        DetPag = _FakeDetPag

        def __new__(cls, detPag):
            return _FakePag(detPag)

    class Cobr:
        Fat = _FakeFat
        Dup = _FakeDup

        def __new__(cls, fat, dup):
            return _FakeCobr(fat, dup)


class _FakeTnfe:
    InfNfe = _FakeInf


class _FakeMod:
    Tnfe = _FakeTnfe


class PagamentoIntegralmenteAVistaUnitTests(TestCase):
    def test_somente_plano_canonico_zero(self):
        self.assertTrue(pagamento_integralmente_a_vista([0]))
        self.assertFalse(pagamento_integralmente_a_vista([]))
        self.assertFalse(pagamento_integralmente_a_vista([30]))
        self.assertFalse(pagamento_integralmente_a_vista([30, 60]))
        self.assertFalse(pagamento_integralmente_a_vista([0, 30]))
        self.assertFalse(pagamento_integralmente_a_vista(None))


class NFeCondicaoPagamentoElegibilidadeTests(TestCase):
    def setUp(self):
        self.pedido, self.item, self.nf = _pedido_nf()

    def test_a_vista(self):
        _marcar_plano(self.nf, [0], 'à vista')
        self.assertEqual(resolver_dias_parcelas_nfe(self.nf), [0])
        self.assertTrue(nfe_venda_integralmente_a_vista(self.nf))
        self.assertFalse(nfe_deve_gerar_cobranca_a_prazo(self.nf))

    def test_a_prazo(self):
        _marcar_plano(self.nf, [30, 60])
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        self.assertTrue(nfe_deve_gerar_cobranca_a_prazo(self.nf))

    def test_misto_nao_e_a_vista(self):
        _marcar_plano(self.nf, [0, 30])
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        self.assertTrue(nfe_deve_gerar_cobranca_a_prazo(self.nf))

    def test_ausente_nao_e_a_vista(self):
        _marcar_plano(self.nf, [], '')
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        self.assertTrue(nfe_deve_gerar_cobranca_a_prazo(self.nf))


class NFeAVistaCobrancaSemAlterarTPagTests(TestCase):
    """
    [0] suprime cobr/dup; tPag permanece na heurística pré-existente de
    build_pag_bindings (presença de duplicatas), sem ler dias_parcelas.
    """

    def setUp(self):
        self.pedido, self.item, self.nf = _pedido_nf()
        _marcar_plano(self.nf, [0], 'à vista')

    def test_nao_gera_duplicatas(self):
        self.assertEqual(gerar_duplicatas_nfe_saida(self.nf), [])

    def test_build_pag_nao_le_dias_parcelas(self):
        fonte = Path(xml_ser.__file__).read_text(encoding='utf-8')
        inicio = fonte.index('def build_pag_bindings')
        fim = fonte.index('def build_cobr_bindings')
        bloco = fonte[inicio:fim]
        # Corpo executável (após docstring): não consulta prazo/condição.
        corpo = bloco.split('"""', 2)[-1]
        self.assertNotIn('dias_parcelas', corpo)
        self.assertNotIn('pagamento_integralmente_a_vista', corpo)
        self.assertNotIn('nfe_venda_integralmente_a_vista', corpo)
        self.assertIn("t_pag = '15' if duplicatas else '01'", corpo)

    def test_cobr_ausente_e_pag_preservado_pela_heuristica_existente(self):
        tot = {'v_nf': '100.00', 'v_desc': '0.00'}
        dups = gerar_duplicatas_nfe_saida(self.nf)
        self.assertEqual(dups, [])
        pag = build_pag_bindings(_FakeMod, tot, duplicatas=dups)
        cobr = build_cobr_bindings(_FakeMod, tot, dups, n_fat='1')
        self.assertIsNone(cobr)
        self.assertEqual(pag.detPag[0].vPag, '100.00')
        # Heurística pré-existente: sem duplicatas → mesmo tPag que build_pag_bindings
        # já produzia (não é decisão nova desta tarefa a partir de dias_parcelas).
        esperado = build_pag_bindings(_FakeMod, tot, duplicatas=[]).detPag[0].tPag
        self.assertEqual(pag.detPag[0].tPag, esperado)

    def test_fin_nfe_ajuste_e_devolucao_usam_tpag_90(self):
        tot = {'v_nf': '900.00', 'v_desc': '0.00'}
        for fin in ('3', '4'):
            with self.subTest(fin_nfe=fin):
                pag = build_pag_bindings(_FakeMod, tot, duplicatas=[{'valor': '10'}], fin_nfe=fin)
                self.assertEqual(pag.detPag[0].tPag, '90')
                self.assertEqual(pag.detPag[0].vPag, '0.00')

    def test_tpag_nao_e_escolhido_pela_regra_de_prazo(self):
        """Dois planos [0] usam a mesma heurística de pag; a regra de prazo não mapeia tPag."""
        tot = {'v_nf': '50.00', 'v_desc': '0.00'}
        nf_b = NFeSaida.objects.get(pk=self.nf.pk)
        _marcar_plano(nf_b, [0], '0')
        dups_a = gerar_duplicatas_nfe_saida(self.nf)
        dups_b = gerar_duplicatas_nfe_saida(nf_b)
        self.assertEqual(dups_a, [])
        self.assertEqual(dups_b, [])
        t_a = build_pag_bindings(_FakeMod, tot, duplicatas=dups_a).detPag[0].tPag
        t_b = build_pag_bindings(_FakeMod, tot, duplicatas=dups_b).detPag[0].tPag
        # Sem fonte canônica distinta de meio de pagamento, ambos seguem a mesma
        # heurística pré-existente — a regra [0] não introduz mapeamento próprio de tPag.
        self.assertEqual(t_a, t_b)
        self.assertEqual(t_a, build_pag_bindings(_FakeMod, tot, duplicatas=None).detPag[0].tPag)


class NFeAPrazoEMistoXmlTests(TestCase):
    def setUp(self):
        self.pedido, self.item, self.nf = _pedido_nf()

    def test_prazo_gera_duplicata_e_cobr(self):
        from apps.comercial.payment_terms import compute_due_dates
        from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida

        _marcar_plano(self.nf, [30], '30')
        base = self.nf.data or date.today()
        self.nf.vencimentos_finais = compute_due_dates(base, [30])
        self.nf.save(update_fields=['vencimentos_finais'])
        aplicar_duplicatas_nfe_saida(self.nf)
        dups = gerar_duplicatas_nfe_saida(self.nf)
        self.assertEqual(len(dups), 1)
        tot = {'v_nf': str(self.nf.valor_total), 'v_desc': '0.00'}
        cobr = build_cobr_bindings(_FakeMod, tot, dups, n_fat='1')
        self.assertIsNotNone(cobr)
        pag = build_pag_bindings(_FakeMod, tot, duplicatas=dups)
        self.assertEqual(pag.detPag[0].tPag, '15')

    def test_misto_elegivel_a_cobranca(self):
        from apps.comercial.payment_terms import compute_due_dates
        from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida

        _marcar_plano(self.nf, [0, 30], '0/30')
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        base = self.nf.data or date.today()
        self.nf.vencimentos_finais = compute_due_dates(base, [0, 30])
        self.nf.save(update_fields=['vencimentos_finais'])
        aplicar_duplicatas_nfe_saida(self.nf)
        dups = gerar_duplicatas_nfe_saida(self.nf)
        self.assertGreaterEqual(len(dups), 1)


class NFeAVistaFinanceiroTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('avista2', 'avista2@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _autorizar_nf(self.nf)
        _marcar_plano(self.nf, [0], 'à vista')

    def test_flags_bloqueiam_geracao(self):
        flags = montar_flags_financeiro_nfe(self.nf)
        self.assertTrue(flags['venda_integralmente_a_vista'])
        self.assertFalse(flags['pode_gerar_contas_receber'])
        self.assertFalse(flags['financeiro_gerado'])
        self.assertEqual(flags['motivo_bloqueio_financeiro'], MSG_VENDA_A_VISTA)

    def test_sem_parcelas_sugeridas(self):
        self.assertEqual(montar_parcelas_sugeridas_nfe(self.nf), [])

    def test_auto_nao_aplica_sem_erro(self):
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertFalse(res['tentado'])
        self.assertFalse(res['gerado'])
        self.assertFalse(res['erro'])
        self.assertTrue(res['venda_integralmente_a_vista'])
        self.assertEqual(res['mensagem'], MSG_VENDA_A_VISTA)
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            0,
        )

    def test_manual_bloqueado(self):
        with self.assertRaises(ValueError) as ctx:
            gerar_contas_receber_de_nfe_autorizada(
                self.nf,
                parcelas=[
                    {
                        'numero_parcela': 1,
                        'vencimento': (self.nf.data or date.today()).isoformat(),
                        'valor': str(self.nf.valor_total),
                    },
                ],
                usuario=self.user,
            )
        self.assertEqual(str(ctx.exception), MSG_VENDA_A_VISTA)

    def test_preview_bloqueado(self):
        with self.assertRaises(ValueError) as ctx:
            preview_contas_receber_de_nfe(self.nf)
        self.assertEqual(str(ctx.exception), MSG_VENDA_A_VISTA)

    def test_endpoint_manual_bloqueado(self):
        r = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/financeiro/gerar-contas-receber/',
            {
                'parcelas': [
                    {
                        'numero_parcela': 1,
                        'vencimento': (self.nf.data or date.today()).isoformat(),
                        'valor': str(Decimal(self.nf.valor_total).quantize(Decimal('0.01'))),
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data.get('detail'), MSG_VENDA_A_VISTA)

    def test_homologacao_a_vista_sem_cr(self):
        nf = _autorizar_nf_homologacao(self.nf)
        _marcar_plano(nf, [0], 'à vista')
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(nf, usuario=self.user)
        self.assertFalse(res['tentado'])
        self.assertFalse(res['erro'])
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=nf.pk,
            ).count(),
            0,
        )


class NFeAPrazoFinanceiroRegressaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('aprazo', 'aprazo@test.com', 'x')
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf = _autorizar_nf(self.nf)
        _marcar_plano(self.nf, [30], '30')
        from apps.comercial.payment_terms import compute_due_dates
        from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida

        base = self.nf.data or date.today()
        self.nf.vencimentos_finais = compute_due_dates(base, [30])
        self.nf.save(update_fields=['vencimentos_finais'])
        aplicar_duplicatas_nfe_saida(self.nf)

    def test_a_prazo_mantem_auto_cr(self):
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        self.assertTrue(gerar_duplicatas_nfe_saida(self.nf))
        res = gerar_contas_receber_automatico_apos_autorizacao_producao(self.nf, usuario=self.user)
        self.assertTrue(res['gerado'])
        self.assertFalse(res['venda_integralmente_a_vista'])
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            1,
        )

    def test_misto_elegivel_a_cr(self):
        _marcar_plano(self.nf, [0, 30], '0/30')
        from apps.comercial.payment_terms import compute_due_dates
        from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida

        base = self.nf.data or date.today()
        self.nf.vencimentos_finais = compute_due_dates(base, [0, 30])
        self.nf.save(update_fields=['vencimentos_finais'])
        aplicar_duplicatas_nfe_saida(self.nf)
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        flags = montar_flags_financeiro_nfe(self.nf)
        self.assertTrue(flags['pode_gerar_contas_receber'])

    def test_condicao_ausente_preserva_fallback_seguro(self):
        _marcar_plano(self.nf, [], '')
        self.assertFalse(nfe_venda_integralmente_a_vista(self.nf))
        parcelas = montar_parcelas_sugeridas_nfe(self.nf)
        self.assertEqual(len(parcelas), 1)
        flags = montar_flags_financeiro_nfe(self.nf)
        self.assertTrue(flags['pode_gerar_contas_receber'])
