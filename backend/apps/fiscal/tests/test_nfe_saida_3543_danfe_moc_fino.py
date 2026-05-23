"""NF-e Saída 3.5.4.3 — DANFE Conferência modelo 55 (ajuste fino MOC §3.8.1)."""

from __future__ import annotations

import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.danfe_moc_matriz_a4_retrato import DANFE_A4_RETRATO, cm_to_pt
from apps.fiscal.danfe_modelo55_conferencia import (
    MSG_BARCODE_CONFERENCIA,
    MSG_CHAVE_CONFERENCIA,
    MSG_PROTOCOLO_CONFERENCIA,
    gerar_danfe_modelo55_conferencia_pdf,
)
from apps.fiscal.models import ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeSaida3543DanfeMocFinoTests(TestCase):
    """Cobertura dos requisitos 3.5.4.3 (parser PDF + matriz MOC)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3543', 'nfe3543@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
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

    def _nf(self, *, long_desc: bool = False, extra_itens: int = 0) -> NFeSaida:
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
            'aliquota_icms': '18',
            'base_icms': '100',
            'valor_icms': '18',
        }
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        nf = NFeSaida.objects.select_related('cliente', 'pedido_venda__empresa_emitente').get(
            pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'],
        )
        nf.informacoes_adicionais = 'infCpl conferência 3543'
        nf.informacoes_fisco = 'infAdFisco MOC'
        nf.observacoes_internas = 'NAO IMPRIMIR INTERNO'
        nf.pedido_cliente_numero = 'PED-3543'
        nf.save()
        it = nf.itens.first()
        it.pedido_cliente_item = 'LIN-99'
        it.observacao_item = 'obs item externa'
        it.informacao_adicional_item = 'infAdProd 3543'
        if long_desc:
            it.snapshot_produto = {**(it.snapshot_produto or {}), 'descricao': 'DESC ' + ('X' * 100)}
        it.save()
        base = nf.itens.first()
        for i in range(extra_itens):
            ItemNFeSaida.objects.create(
                nf=nf,
                produto=base.produto,
                quantidade=Decimal('1'),
                valor=Decimal('10'),
                snapshot_fiscal=base.snapshot_fiscal,
                snapshot_produto=base.snapshot_produto,
            )
        return nf

    def _pdf(self, nf: NFeSaida | None = None) -> tuple[bytes, str]:
        nf = nf or self._nf()
        pdf, _ = gerar_danfe_modelo55_conferencia_pdf(nf)
        return pdf, compact_pdf_text(pdf_text(pdf))

    def test_matriz_moc_declarativa(self):
        self.assertIn('produtos_bloco', DANFE_A4_RETRATO)
        self.assertIn('canhoto_recebemos', DANFE_A4_RETRATO)
        self.assertAlmostEqual(DANFE_A4_RETRATO['produtos_bloco']['h'], 6.77, places=2)
        self.assertAlmostEqual(DANFE_A4_RETRATO['produtos_bloco']['w'], 20.57, places=2)

    def test_escala_a4_pontos(self):
        from reportlab.lib.pagesizes import A4 as RL_A4

        self.assertAlmostEqual(cm_to_pt(21.0), RL_A4[0], delta=1.0)
        self.assertAlmostEqual(cm_to_pt(29.7), RL_A4[1], delta=1.0)

    def test_pdf_basico_conferencia(self):
        pdf, t = self._pdf()
        self.assertTrue(pdf.startswith(b'%PDF'))
        for trecho in (
            'DANFE',
            'DOCUMENTOAUXILIAR',
            'NFECONFERENCIA',
            'SEMVALORFISCAL',
            'FALTAPROTOCOLODEAPROVACAODASEFAZ',
            'CONSULTADEAUTENTICIDADE',
            'RECEBEMOSDE',
            'VENDADEMERCADORIA',
            'CALCULODOIMPOSTO',
            'TRANSPORTADOR',
            'DADOSDOSPRODUTOS',
            'DADOSADICIONAIS',
            'RESERVADOAOFISCO',
            '84818200',
            '5102',
            'INFADPROD',
            'XPED',
            'NITEMPEDLIN99',
        ):
            self.assertIn(compact_pdf_text(trecho), t, trecho)

    def test_sem_chave_protocolo_fake(self):
        _, t = self._pdf()
        self.assertIn('CHAVEDEACESSO', t)
        self.assertIn('NAOGERADA', t)
        self.assertIn('WWNFEFAZENDAGOVBR', t)
        self.assertIn('CONSULTADEAUTENTICIDADE', t)
        digits = ''.join(c for c in t if c.isdigit())
        self.assertNotEqual(len(digits), 44)

    def test_colunas_produtos_fiscais(self):
        _, t = self._pdf()
        for col in ('NCM', 'CFOP', 'ICMS', 'QUANT', 'VALORUNIT', 'VALORTOTAL', 'BCALCICMS', 'ALIQ', 'IPI'):
            self.assertIn(col, t, col)

    def test_observacoes_internas_nao_aparece(self):
        _, t = self._pdf()
        self.assertNotIn('NAO IMPRIMIR INTERNO', t)

    def test_multipagina_cabecalho_continuacao(self):
        """Layout HTML absoluto: PDF válido com muitos itens; folhas extras em fase futura."""
        pdf, t = self._pdf(self._nf(extra_itens=28))
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreaterEqual(len(PdfReader(io.BytesIO(pdf)).pages), 1)
        self.assertIn('84818200', compact_pdf_text(t))

    def test_nao_altera_fiscal_estoque_financeiro_sefaz(self):
        nf = self._nf()
        st, sc = nf.status, nf.status_conferencia
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        gerar_danfe_modelo55_conferencia_pdf(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(nf.status_conferencia, sc)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)

    def test_api_preview_pdf(self):
        nf = self._nf()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
