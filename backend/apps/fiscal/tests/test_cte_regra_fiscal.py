"""Regra fiscal FRETE_TRANSPORTE obrigatória na conferência/CP do CT-e."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.cadastros.models import Fornecedor, Transportadora
from apps.fiscal.cte_financeiro import CteFinanceiroErro, gerar_contas_pagar_de_cte
from apps.fiscal.cte_historico_conferencia import ConferenciaCteErro, conferir_cte_importado
from apps.fiscal.cte_regra_fiscal import MSG_SEM_REGRA_CTE, avaliar_regra_fiscal_cte
from apps.fiscal.models import CTeHistoricoImportado
from apps.fiscal.tests.cte_regra_fiscal_fixtures import CFOP_CTE_TESTE, garantir_regra_frete_cte
from apps.regras_fiscais.models import RegraFiscalEntrada


def _dh():
    return timezone.make_aware(datetime(2026, 8, 1, 10, 0, 0))


def _payload_conferir():
    return {
        'observacao': 'ok',
        'confirmar_tomador': True,
        'confirmar_transportadora': True,
        'confirmar_valores': True,
        'confirmar_documentos_referenciados': True,
    }


class CteRegraFiscalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='ctereg', password='x')
        self.dh = _dh()
        self.transp = Transportadora.objects.create(razao_social='Rodovia LTDA', cnpj='11222333000144')
        Fornecedor.objects.create(razao_social='Rodovia LTDA', cnpj='11222333000144')

    def _cte(self, **kw):
        return CTeHistoricoImportado.objects.create(
            chave_acesso=kw.pop('chave', '7' * 44),
            numero=kw.pop('numero', '1'),
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            cfop=kw.pop('cfop', CFOP_CTE_TESTE),
            valor_total_servico=Decimal('100.00'),
            valor_receber=Decimal('100.00'),
            transportadora=self.transp,
            status_conferencia=CTeHistoricoImportado.StatusConferencia.PROCESSADO,
            **kw,
        )

    def test_sem_regra_bloqueia_conferencia(self):
        cte = self._cte()
        av = avaliar_regra_fiscal_cte(cte)
        self.assertEqual(av['status'], 'SEM_REGRA')
        with self.assertRaises(ConferenciaCteErro) as ctx:
            conferir_cte_importado(cte, self.user, _payload_conferir())
        self.assertIn('Frete / transporte', str(ctx.exception))

    def test_com_regra_permite_conferencia(self):
        garantir_regra_frete_cte(cfop=CFOP_CTE_TESTE)
        cte = self._cte()
        av = avaliar_regra_fiscal_cte(cte)
        self.assertEqual(av['status'], 'OK')
        conferir_cte_importado(cte, self.user, _payload_conferir())
        cte.refresh_from_db()
        self.assertTrue(cte.apto_operacional)

    def test_regra_compra_nao_casa_cte(self):
        RegraFiscalEntrada.objects.create(
            nome='Compra 5353',
            ativo=True,
            prioridade=10,
            cfop=CFOP_CTE_TESTE,
            cfop_origem=CFOP_CTE_TESTE,
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        cte = self._cte()
        self.assertEqual(avaliar_regra_fiscal_cte(cte)['status'], 'SEM_REGRA')

    def test_sem_regra_bloqueia_cp_mesmo_conferido_manual(self):
        """Se status conferido sem regra (legado), CP ainda exige regra."""
        cte = self._cte()
        cte.status_conferencia = CTeHistoricoImportado.StatusConferencia.CONFERIDO
        cte.apto_operacional = True
        cte.situacao_financeira_frete = CTeHistoricoImportado.SituacaoFinanceiraFrete.A_PAGAR
        cte.save(update_fields=['status_conferencia', 'apto_operacional', 'situacao_financeira_frete'])
        with self.assertRaises(CteFinanceiroErro) as ctx:
            gerar_contas_pagar_de_cte(cte, usuario=self.user)
        self.assertIn(MSG_SEM_REGRA_CTE[:40], str(ctx.exception))

    def test_pago_avista_nao_gera_cp(self):
        garantir_regra_frete_cte(cfop=CFOP_CTE_TESTE)
        cte = self._cte(chave='6' * 44)
        conferir_cte_importado(cte, self.user, _payload_conferir())
        from apps.fiscal.cte_financeiro import definir_situacao_financeira_frete, montar_flags_financeiro_cte

        definir_situacao_financeira_frete(cte, situacao='PAGO_AVISTA', usuario=self.user)
        cte.refresh_from_db()
        flags = montar_flags_financeiro_cte(cte)
        self.assertEqual(flags['situacao_financeira_frete'], 'PAGO_AVISTA')
        self.assertFalse(flags['pode_gerar_contas_pagar'])
        with self.assertRaises(CteFinanceiroErro):
            gerar_contas_pagar_de_cte(cte, usuario=self.user)
