"""Fase Saída 3.7 — Reforma Tributária guiada e Recomendações NF-e/DANFE."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.regras_fiscais.cenario_fiscal_saida import (
    garantir_cenario_saida_padrao,
    montar_matriz_escopo_saida,
    serializar_configuracao_matriz_saida,
)
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida
from apps.regras_fiscais.recomendacoes_nfe_config import (
    contar_recomendacoes_nfe,
    normalizar_recomendacoes_nfe,
    recomendacoes_nfe_preenchidas,
)
from apps.regras_fiscais.reforma_tributaria_config import (
    normalizar_reforma_tributaria,
    resumo_reforma_tributaria,
)
from apps.regras_fiscais.saida_fiscal import buscar_regra_fiscal_saida


class ReformaRecomendacoesSaidaTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()
        self.escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818300',
        )

    def test_reforma_tributaria_cst_classificacao(self):
        regra = RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            reforma_tributaria={
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_cbs': '0.9',
            },
        )
        norm = normalizar_reforma_tributaria(regra.reforma_tributaria)
        self.assertEqual(norm['cst_ibs_cbs'], '000')
        self.assertEqual(norm['classificacao_tributaria'], '000001')
        self.assertIn('CST 000', resumo_reforma_tributaria(regra.reforma_tributaria))

    def test_recomendacoes_nfe_json(self):
        regra = RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            recomendacoes_nfe={
                'danfe_paisagem': True,
                'ordenar_itens_por_descricao': True,
                'chave_desconhecida': True,
            },
        )
        norm = normalizar_recomendacoes_nfe(regra.recomendacoes_nfe)
        self.assertTrue(norm['danfe_paisagem'])
        self.assertTrue(norm['ordenar_itens_por_descricao'])
        self.assertNotIn('chave_desconhecida', norm)
        self.assertTrue(recomendacoes_nfe_preenchidas(norm))
        self.assertEqual(contar_recomendacoes_nfe(norm), 2)

    def test_recomendacoes_null_compativel(self):
        regra = RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
        )
        self.assertIsNone(regra.recomendacoes_nfe)
        self.assertFalse(recomendacoes_nfe_preenchidas(regra.recomendacoes_nfe))

    def test_matriz_badges_reforma_e_recomendacoes(self):
        regra = RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            reforma_tributaria={'cst_ibs_cbs': '400'},
            recomendacoes_nfe={'danfe_paisagem': True},
        )
        cfg = serializar_configuracao_matriz_saida(regra)
        self.assertTrue(cfg['tem_reforma'])
        self.assertTrue(cfg['tem_recomendacoes_nfe'])
        self.assertEqual(cfg['qtd_recomendacoes_nfe'], 1)
        matriz = montar_matriz_escopo_saida(self.escopo)
        self.assertEqual(len(matriz['configuracoes']), 1)

    def test_api_expoe_recomendacoes_nfe(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user('rf_saida', 'rf@test.com', 'x')
        client = APIClient()
        client.force_authenticate(user)
        regra = RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            aliquota_icms=Decimal('18'),
            aliquota_pis=Decimal('1.65'),
            aliquota_cofins=Decimal('7.6'),
            recomendacoes_nfe={'exibir_email_destinatario': True},
        )
        url = reverse('regrafiscal-saida-detail', args=[regra.pk])
        r = client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertIn('recomendacoes_nfe', body)
        self.assertTrue(body['recomendacoes_nfe']['exibir_email_destinatario'])

    def test_motor_inclui_flags_informativas(self):
        RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            aliquota_icms=Decimal('18'),
            aliquota_pis=Decimal('1.65'),
            aliquota_cofins=Decimal('7.6'),
            reforma_tributaria={'cst_ibs_cbs': '000'},
            recomendacoes_nfe={'danfe_paisagem': True},
        )
        from django.test import override_settings

        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True):
            r = buscar_regra_fiscal_saida(ncm='84818300', uf_origem='SP', uf_destino='RJ')
        self.assertTrue(r['tem_reforma_configurada'])
        self.assertTrue(r['tem_recomendacoes_nfe'])
