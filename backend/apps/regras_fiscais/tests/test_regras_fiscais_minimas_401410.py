"""ERP 4.0.14.10 — regras fiscais mínimas para produção."""

from __future__ import annotations

from django.test import TestCase

from apps.cadastros.models import Empresa
from apps.core.preparacao_limpeza_producao import _contar_preservados, executar_dry_run_limpeza_producao
from apps.core.pre_producao import gerar_relatorio_pre_producao
from apps.core.prontidao_producao import executar_verificacao_prontidao
from apps.produtos.models import Produto
from apps.regras_fiscais.models import RegraFiscal
from apps.regras_fiscais.regras_fiscais_minimas import validar_regras_fiscais_minimas


class RegrasFiscaisMinimas401410Tests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social='NEXUS TESTE 401410',
            cnpj='59443075000130',
            uf='SP',
            regime_tributario='Simples Nacional',
        )

    def _criar_regra_venda_minima(self):
        return RegraFiscal.objects.create(
            ncm='84818099',
            uf_origem='SP',
            uf_destino='SP',
            operacao='Saída',
            cfop='5102',
            cst_icms='102',
            aliquota_icms=0,
        )

    def test_critico_sem_regra_fiscal(self):
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('nenhuma regra fiscal', msgs)

    def test_critico_sem_regime_tributario(self):
        self.empresa.regime_tributario = ''
        self.empresa.save(update_fields=['regime_tributario'])
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('regime tributário', msgs)

    def test_critico_regra_sem_cfop(self):
        RegraFiscal.objects.create(
            ncm='84818099',
            uf_origem='SP',
            uf_destino='SP',
            operacao='Saída',
            cfop='',
            cst_icms='102',
        )
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('cfop', msgs)

    def test_critico_regra_sem_cst(self):
        RegraFiscal.objects.create(
            ncm='84818099',
            uf_origem='SP',
            uf_destino='SP',
            operacao='Saída',
            cfop='5102',
            cst_icms='',
        )
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('cst', msgs)

    def test_ok_com_regra_minima_e_produto_ncm(self):
        self._criar_regra_venda_minima()
        Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='P401410',
            descricao='Válvula teste',
            unidade='PC',
            ncm='84818099',
        )
        res = validar_regras_fiscais_minimas()
        self.assertTrue(any(a['nivel'] == 'ok' for a in res['ok']))

    def test_prontidao_inclui_secao_fiscal(self):
        pront = executar_verificacao_prontidao()
        self.assertIn('fiscal', pront)
        self.assertIn('metricas', pront['fiscal'])

    def test_relatorio_pre_producao_secao_fiscal(self):
        rel = gerar_relatorio_pre_producao()
        self.assertEqual(rel['versao'], 'ERP 4.0.14.10.1')
        self.assertIn('fiscal', rel['prontidao'])

    def test_dry_run_preserva_regras_fiscais(self):
        self._criar_regra_venda_minima()
        antes = RegraFiscal.objects.count()
        rel = executar_dry_run_limpeza_producao()
        self.assertEqual(RegraFiscal.objects.count(), antes)
        self.assertGreaterEqual(rel['preservados']['regras_fiscais'], 1)

    def test_contar_preservados_inclui_saida_entrada(self):
        counts = _contar_preservados()
        self.assertIn('regras_fiscais_saida', counts)
        self.assertIn('regras_fiscais_entrada', counts)

    def test_produto_sem_ncm_critico(self):
        self._criar_regra_venda_minima()
        Produto.objects.create(
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='SEMNC401410',
            descricao='Sem NCM',
            unidade='PC',
        )
        res = validar_regras_fiscais_minimas()
        msgs = ' '.join(c['mensagem'] for c in res['criticos']).lower()
        self.assertIn('sem ncm', msgs)
