"""ERP 4.0.13.6.7 — Layout DANFE conferência: duplicatas e quadro de totais."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.comercial.payment_terms import compute_due_dates
from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.danfe_conferencia_layout import (
    FATURA_EXTRA_LINHA_DUP_CM,
    MAX_DUPLICATAS_NO_BLOCO,
    calcular_layout_fatura_duplicatas,
    preparar_duplicatas_danfe,
)
from apps.fiscal.danfe_render import RENDER_ENGINES_OFICIAIS, render_danfe_conferencia_pdf
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_40133_duplicatas import _pedido_com_prazo, _pedido_multi_parcelas
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.tests.test_nfe_saida_354_danfe_conferencia import _regra
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _nf_com_n_duplicatas(n: int) -> NFeSaida:
    qtd_fat = '2'
    if n == 1:
        pedido, item, _ = _pedido_com_prazo(valor=Decimal('500'), dias=30, qtd=Decimal('2'), preco=Decimal('250'))
    elif n == 3:
        pedido, item = _pedido_multi_parcelas()
        qtd_fat = '3'
    else:
        pedido, item = _pedido_item(qtd=Decimal('1'), preco=Decimal('100'))
        qtd_fat = '1'
        pedido.valor_total = Decimal('100') * n
        dias = [30 * (i + 1) for i in range(n)]
        pedido.condicao_pagamento_texto = '/'.join(str(d) for d in dias)
        pedido.dias_parcelas = dias
        pedido.quantidade_parcelas = n
        pedido.vencimentos_previstos = compute_due_dates(pedido.data, dias)
        pedido.save(
            update_fields=[
                'valor_total',
                'condicao_pagamento_texto',
                'dias_parcelas',
                'quantidade_parcelas',
                'vencimentos_previstos',
            ],
        )
    fat = _faturamento_pronto(pedido, item, qtd=qtd_fat)
    nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
    aplicar_duplicatas_nfe_saida(nf)
    nf.refresh_from_db()
    return nf


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DanfeLayoutDuplicatas401367Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('401367', '401367@test.com', 'x')
        cenario = garantir_cenario_saida_padrao()
        escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
            cenario=cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818200',
            defaults={},
        )
        RegraFiscalSaida.objects.update_or_create(
            escopo=escopo,
            cenario=cenario,
            uf_origem='SP',
            uf_destino='RJ',
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
            defaults={'nome': 'R', 'cfop_venda': '5102', 'cst_icms': '00', 'aliquota_icms': Decimal('18')},
        )

    def _pdf(self, nf: NFeSaida) -> str:
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import brazil_fiscal_report_disponivel

        if not brazil_fiscal_report_disponivel():
            self.skipTest('BrazilFiscalReport não instalado')
        pdf, meta = render_danfe_conferencia_pdf({'nfe_saida_id': nf.pk}, nfe_saida_id=nf.pk)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(meta.get('render_engine'), RENDER_ENGINES_OFICIAIS)
        return pdf_text(pdf)

    def test_preparar_10_duplicatas_no_bloco_overflow(self):
        dups = [{'numero': f'{i:03d}', 'vencimento': '01/01/2026', 'valor': 'R$ 10,00'} for i in range(1, 13)]
        visiveis, overflow = preparar_duplicatas_danfe(dups)
        self.assertEqual(len(visiveis), MAX_DUPLICATAS_NO_BLOCO)
        self.assertIn('011', overflow)

    def test_layout_6_duplicatas_segunda_linha(self):
        layout = calcular_layout_fatura_duplicatas(6)
        self.assertEqual(layout['linhas_dup'], 2)
        self.assertAlmostEqual(float(layout['extra_offset_cm']), FATURA_EXTRA_LINHA_DUP_CM)

    def test_layout_5_duplicatas_uma_linha(self):
        layout = calcular_layout_fatura_duplicatas(5)
        self.assertEqual(layout['linhas_dup'], 1)
        self.assertEqual(float(layout['extra_offset_cm']), 0.0)

    def test_layout_labels_imposto_multiline(self):
        from apps.fiscal.danfe_conferencia_layout import IMPOSTO_LABELS_DISPLAY

        self.assertIn('\n', IMPOSTO_LABELS_DISPLAY['imp_valor_produtos'])

    def test_pdf_bfr_valor_total_produtos_duas_linhas(self):
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
            DanfeNexus,
            XML_NFE_EXEMPLO_POC,
            _montar_config_danfe,
        )
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import _importar_danfe

        _, DanfeConfig = _importar_danfe()
        cfg = _montar_config_danfe(DanfeConfig)
        pdf = DanfeNexus.render(
            XML_NFE_EXEMPLO_POC,
            cfg,
            marca_dagua='DANFE DE CONFERÊNCIA\nSEM VALOR FISCAL',
            cancelada_bfr=False,
        )
        c = compact_pdf_text(pdf_text(pdf))
        self.assertIn('VALORTOTAL', c.replace(' ', ''))
        self.assertIn('DOSPRODUTOS', c)
        # Texto completo (não cortar no «PRODUTO» sem «S»)
        self.assertRegex(c, r'VALORTOTAL.*DOSPRODUTOS')

    def test_pdf_1_duplicata_bfr(self):
        nf = _nf_com_n_duplicatas(1)
        c = compact_pdf_text(self._pdf(nf))
        self.assertIn('001', c)
        self.assertIn('VALORTOTAL', c.replace(' ', ''))
        self.assertIn('DOSPRODUTOS', c)

    def test_pdf_3_duplicatas_bfr(self):
        nf = _nf_com_n_duplicatas(3)
        c = compact_pdf_text(self._pdf(nf))
        self.assertIn('001', c)
        self.assertIn('002', c)
        self.assertIn('003', c)

    def test_pdf_6_duplicatas_bfr(self):
        nf = _nf_com_n_duplicatas(6)
        c = compact_pdf_text(self._pdf(nf))
        for i in range(1, 7):
            self.assertIn(f'{i:03d}', c)

    def test_pdf_10_duplicatas_bfr(self):
        nf = _nf_com_n_duplicatas(10)
        c = compact_pdf_text(self._pdf(nf))
        self.assertIn('010', c)
        self.assertNotIn('011', c)

    def test_pdf_12_duplicatas_overflow_em_dados_adicionais(self):
        nf = _nf_com_n_duplicatas(12)
        dados = montar_dados_danfe_conferencia(nf)
        self.assertIn('Demais duplicatas', dados.get('informacoes_complementares') or '')
        pdf, meta = render_danfe_conferencia_pdf({'nfe_saida_id': nf.pk}, nfe_saida_id=nf.pk)
        self.assertIn(meta.get('render_engine'), RENDER_ENGINES_OFICIAIS)
        c = compact_pdf_text(pdf_text(pdf))
        self.assertIn('DEMAISDUPLICATAS', c)

    def test_pdf_10_duplicatas_bfr_grade(self):
        nf = _nf_com_n_duplicatas(10)
        c = compact_pdf_text(self._pdf(nf))
        self.assertIn('010', c)
        self.assertIn('DUPLICATAS', c)

    def test_valor_total_produtos_visivel(self):
        nf = _nf_com_n_duplicatas(1)
        c = compact_pdf_text(self._pdf(nf))
        self.assertIn('50000', c.replace('.', '').replace(',', ''))
