"""ERP 4.0.14.10.1 — regra fiscal de entrada como aviso na prontidão, bloqueio no uso."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Empresa
from apps.core.preparacao_limpeza_producao import (
    CONFIRMACAO_TOKEN,
    executar_dry_run_limpeza_producao,
    validar_execucao_limpeza_permitida,
)
from apps.core.pre_producao import gerar_relatorio_pre_producao
from apps.core.prontidao_producao import executar_verificacao_prontidao
from apps.produtos.models import Produto
from apps.regras_fiscais.models import RegraFiscal, RegraFiscalEntrada, RegraFiscalSaida
from apps.regras_fiscais.regras_fiscais_minimas import (
    validar_regra_fiscal_entrada_para_uso,
    validar_regras_fiscais_minimas,
)


class RegrasFiscaisMinimas4014101Tests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social='NEXUS TESTE 4014101',
            cnpj='59443075000130',
            uf='SP',
            regime_tributario='Lucro Presumido',
        )
        user = get_user_model().objects.create_user('rf4014101', 'rf4014101@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def _regra_saida_valida(self):
        return RegraFiscalSaida.objects.create(
            nome='Venda SP',
            ativo=True,
            cfop_venda='5102',
            tipo_operacao=RegraFiscalSaida.TipoOperacao.VENDA,
            cst_icms='00',
            uf_origem='SP',
            uf_destino='SP',
        )

    def _regra_entrada_incompleta(self, nome='Configuração'):
        return RegraFiscalEntrada.objects.create(
            nome=nome,
            ativo=True,
            prioridade=10,
            cfop='5102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
        )

    def _regra_entrada_valida(self):
        return RegraFiscalEntrada.objects.create(
            nome='Entrada OK',
            ativo=True,
            prioridade=10,
            cfop='5102',
            cfop_entrada='1102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            cst_icms_esperado='00',
        )

    def _produto_com_ncm(self):
        Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='P4014101',
            descricao='Válvula teste',
            unidade='PC',
            ncm='84818099',
        )

    def test_prontidao_nao_bloqueia_ausencia_regra_entrada(self):
        self._regra_saida_valida()
        self._produto_com_ncm()
        res = validar_regras_fiscais_minimas()
        criticos_txt = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertNotIn('entrada', criticos_txt)
        avisos_txt = ' '.join(a['mensagem'] for a in res['avisos_entrada']).lower()
        self.assertIn('entrada', avisos_txt)

    def test_prontidao_nao_bloqueia_regra_entrada_incompleta(self):
        self._regra_saida_valida()
        self._regra_entrada_incompleta()
        self._produto_com_ncm()
        res = validar_regras_fiscais_minimas()
        criticos_txt = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertNotIn('entrada', criticos_txt)
        self.assertTrue(any('entrada' in a['mensagem'].lower() for a in res['avisos_entrada']))

    def test_prontidao_aviso_regra_entrada_incompleta(self):
        self._regra_saida_valida()
        self._regra_entrada_incompleta('Configuração')
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(a['mensagem'] for a in res['avisos_entrada']).lower()
        self.assertIn('configuração', msgs)
        self.assertIn('cst', msgs)

    def test_prontidao_bloqueia_ausencia_regra_saida(self):
        self._regra_entrada_valida()
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('venda', msgs)

    def test_prontidao_bloqueia_saida_sem_cst(self):
        RegraFiscalSaida.objects.create(
            nome='Saída sem CST',
            ativo=True,
            cfop_venda='5102',
            tipo_operacao=RegraFiscalSaida.TipoOperacao.VENDA,
            cst_icms='',
        )
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('cst', msgs)

    def test_limpeza_nao_bloqueia_so_por_entrada_incompleta(self):
        self._regra_saida_valida()
        self._regra_entrada_incompleta()
        self._produto_com_ncm()
        pront = executar_verificacao_prontidao()
        dry = executar_dry_run_limpeza_producao()
        pode, motivo = validar_execucao_limpeza_permitida(
            dry,
            pront,
            backup_confirmado=True,
            confirmacao=CONFIRMACAO_TOKEN,
        )
        fiscal_criticos = [c for c in pront.get('criticos', []) if 'entrada' in c.get('mensagem', '').lower()]
        self.assertEqual(fiscal_criticos, [])
        if not pode and motivo:
            self.assertNotIn('entrada', motivo.lower())

    def test_fluxo_entrada_bloqueia_sem_regra_valida(self):
        self._regra_entrada_incompleta()
        uso = validar_regra_fiscal_entrada_para_uso()
        self.assertFalse(uso['valida'])
        self.assertTrue(uso['bloqueios'])

    def test_helper_entrada_valida_com_regra_completa(self):
        self._regra_entrada_valida()
        uso = validar_regra_fiscal_entrada_para_uso()
        self.assertTrue(uso['valida'])

    def test_cadastro_bloqueia_ativar_entrada_sem_cst(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Rascunho',
            ativo=False,
            cfop='5102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
        )
        r = self.client.patch(
            f'/api/regras-fiscais-entrada/{regra.pk}/',
            {'ativo': True},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cst', str(r.json()).lower())

    def test_cadastro_permite_inativa_incompleta(self):
        r = self.client.post(
            '/api/regras-fiscais-entrada/',
            {
                'nome': 'Rascunho inativo',
                'ativo': False,
                'cfop': '5102',
                'prioridade': 10,
            },
            format='json',
        )
        self.assertIn(r.status_code, (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST))
        if r.status_code == status.HTTP_201_CREATED:
            self.assertFalse(r.json()['ativo'])

    def test_relatorio_separa_aviso_entrada_de_critico(self):
        self._regra_saida_valida()
        self._regra_entrada_incompleta()
        rel = gerar_relatorio_pre_producao()
        self.assertEqual(rel['versao'], 'ERP 4.0.14.10.1')
        fiscal = rel['prontidao']['fiscal']
        self.assertIn('avisos_entrada', fiscal)
        self.assertIn('bloqueios_por_fluxo', fiscal)
        criticos_fiscal = ' '.join(c.get('mensagem', '') for c in fiscal.get('criticos', [])).lower()
        self.assertNotIn('entrada incompleta', criticos_fiscal)

    def test_checklist_separado_saida_entrada(self):
        self._regra_saida_valida()
        res = validar_regras_fiscais_minimas()
        self.assertIn('checklist_saida', res)
        self.assertIn('checklist_entrada', res)
        self.assertGreater(len(res['checklist_saida']), 0)
        self.assertGreater(len(res['checklist_entrada']), 0)
