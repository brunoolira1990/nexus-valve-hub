"""CT-e — rateio de frete + geração de CP (+ impostos)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor, Transportadora
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.cte_financeiro import (
    gerar_contas_pagar_de_cte,
    salvar_rateio_frete_cte,
    sugerir_rateio_frete_cte,
    valor_base_frete_cte,
)
from apps.fiscal.cte_historico_conferencia import conferir_cte_importado
from apps.fiscal.models import CTeHistoricoImportado, NFeEntradaHistoricaImportada
from apps.fiscal.tests.cte_regra_fiscal_fixtures import CFOP_CTE_TESTE, garantir_regra_frete_cte


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


class CteFreteFinanceiroTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='ctefrete', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.dh = _dh()
        self.transp = Transportadora.objects.create(
            razao_social='Transp Frete LTDA',
            cnpj='12345678000199',
        )
        self.forn = Fornecedor.objects.create(
            razao_social='Transp Frete LTDA',
            cnpj='12345678000199',
        )
        garantir_regra_frete_cte()

    def _cte(self, **kw):
        chaves = kw.pop('chaves', [])
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso=kw.pop('chave', '9' * 44),
            numero=kw.pop('numero', '500'),
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            cfop=kw.pop('cfop', CFOP_CTE_TESTE),
            valor_total_servico=Decimal('300.00'),
            valor_receber=Decimal('300.00'),
            icms_valor=Decimal('36.00'),
            transportadora=self.transp,
            chaves_nfe_vinculadas=chaves,
            status_conferencia=CTeHistoricoImportado.StatusConferencia.PROCESSADO,
            reforma_e_outros_json={
                'ibscbs': {'presente': True, 'cbs_valor': 10.0, 'ibs_valor': 5.0},
            },
            **kw,
        )
        return cte

    def test_rateio_proporcional_e_cp_com_impostos(self):
        ch1, ch2 = '1' * 44, '2' * 44
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=ch1,
            numero='10',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('200.00'),
        )
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=ch2,
            numero='11',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
            valor_total_nf=Decimal('100.00'),
        )
        cte = self._cte(chaves=[ch1, ch2])
        conferir_cte_importado(cte, self.user, _payload_conferir())
        cte.refresh_from_db()
        from apps.fiscal.cte_financeiro import definir_situacao_financeira_frete

        definir_situacao_financeira_frete(cte, situacao='A_PAGAR', usuario=self.user)
        cte.refresh_from_db()
        self.assertEqual(valor_base_frete_cte(cte), Decimal('300.00'))

        sug = sugerir_rateio_frete_cte(cte)
        self.assertEqual(sug['metodo'], 'PROPORCIONAL_VALOR_NFE')
        self.assertEqual(len(sug['linhas']), 2)
        valores = sorted(Decimal(l['valor_frete']) for l in sug['linhas'])
        self.assertEqual(valores, [Decimal('100.00'), Decimal('200.00')])

        salvar_rateio_frete_cte(cte, linhas=sug['linhas'], metodo=sug['metodo'], usuario=self.user)
        cte.refresh_from_db()
        self.assertTrue(cte.rateio_frete_json.get('linhas'))

        out = gerar_contas_pagar_de_cte(cte, gerar_impostos_separados=True, usuario=self.user)
        self.assertTrue(out['titulo_frete_id'])
        # ICMS 36 + CBS 10 + IBS 5
        self.assertEqual(len(out['titulos_tributo_ids']), 3)
        titulos = TituloFinanceiro.objects.filter(origem_tipo=TituloFinanceiro.OrigemTipo.CTE, origem_id=cte.pk)
        self.assertEqual(titulos.count(), 4)
        frete = titulos.get(pk=out['titulo_frete_id'])
        self.assertEqual(frete.valor_original, Decimal('300.00'))
        self.assertEqual(frete.fornecedor_id, self.forn.id)

    def test_api_sugerir_rateio_exige_conferido(self):
        cte = self._cte(chave='8' * 44)
        url = reverse('cte-hist-importado-sugerir-rateio-frete', args=[cte.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
