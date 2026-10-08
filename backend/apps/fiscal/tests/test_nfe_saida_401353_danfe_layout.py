"""ERP 4.0.13.5.3 — layout DANFE/NF-e de conferência (seções, duplicatas, marca d'água)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.comercial.payment_terms import compute_due_dates
from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.danfe_render import render_danfe_conferencia_pdf
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_40133_duplicatas import _nf_com_prazo
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _section_index(text: str, label: str) -> int:
    return text.upper().find(label.upper())


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeSaida401353DanfeLayoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('401353', '401353@test.com', 'x')
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

    def _pdf_text(self, nf: NFeSaida) -> str:
        dados = montar_dados_danfe_conferencia(nf)
        pdf, _ = render_danfe_conferencia_pdf(dados, nfe_saida_id=nf.pk)
        self.assertTrue(pdf.startswith(b'%PDF'))
        return pdf_text(pdf)

    def test_danfe_conferencia_renderiza_sem_excecao(self):
        pedido, item = _pedido_item()
        fat = _faturamento_pronto(pedido, item)
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        t = self._pdf_text(nf)
        self.assertIn('DANFE', t.upper())

    def test_marca_dagua_discreta_sem_protocolo_grande(self):
        nf, _ = _nf_com_prazo()
        c = compact_pdf_text(self._pdf_text(nf))
        self.assertIn('DANFEDECONFERENCIA', c)
        self.assertIn('SEMVALORFISCAL', c)
        self.assertNotIn('FALTAPROTOCOLODEAPROVACAODASEFAZ', c)

    def test_duplicata_na_secao_fatura_antes_imposto(self):
        nf, venc = _nf_com_prazo()
        raw = self._pdf_text(nf)
        c = compact_pdf_text(raw)
        idx_fatura = _section_index(raw, 'FATURA')
        idx_imposto = _section_index(raw, 'CÁLCULO DO IMPOSTO')
        idx_produtos = max(
            _section_index(raw, 'DADOS DOS PRODUTOS'),
            _section_index(raw, 'PRODUTOS / SERVI'),
            _section_index(c, 'DADOSDOSPRODUTOS'),
        )
        self.assertGreater(idx_imposto, idx_fatura)
        self.assertGreater(idx_produtos, idx_imposto)
        self.assertIn('001', c)
        self.assertIn(venc.strftime('%d/%m/%Y').replace('/', ''), c.replace('/', ''))
        # Duplicata não deve aparecer colada ao rótulo de hora de saída
        hora_pos = c.find('HORAENTRADA/SAIDA')
        dup_pos = c.find('001')
        if hora_pos >= 0 and dup_pos >= 0:
            self.assertTrue(dup_pos > hora_pos + 20 or 'FATURA' in c[:dup_pos])

    def test_duplicata_valor_e_destinatario_integridade(self):
        nf, venc = _nf_com_prazo()
        raw = self._pdf_text(nf)
        c = compact_pdf_text(raw)
        self.assertIn('DESTINATARIO', c.replace('Á', 'A'))
        self.assertIn('5000', c.replace('.', '').replace(',', ''))
        self.assertIn('84818200', c)

    def test_dados_adicionais_no_final(self):
        nf, _ = _nf_com_prazo()
        raw = self._pdf_text(nf)
        idx_prod = _section_index(raw, 'DADOS DOS PRODUTOS')
        idx_adic = _section_index(raw, 'DADOS ADICIONAIS')
        self.assertGreater(idx_adic, idx_prod)
