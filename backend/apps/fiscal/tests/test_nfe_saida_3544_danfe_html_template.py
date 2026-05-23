"""NF-e 3.5.4.4 — DANFE Conferência template HTML/WeasyPrint."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.danfe_render import render_danfe_conferencia_pdf
from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.models import ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, norm_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeSaida3544DanfeHtmlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3544', 'nfe3544@test.com', 'x')
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

    def _nf(self, *, long_desc: bool = False, extra: int = 0, transporte: bool = False) -> NFeSaida:
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
        nf = NFeSaida.objects.select_related('cliente', 'transportadora').get(
            pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'],
        )
        nf.informacoes_adicionais = 'Info complementar template HTML'
        nf.informacoes_fisco = 'Reservado fisco teste'
        nf.observacoes_internas = 'NAO IMPRIMIR SECRETO'
        if transporte:
            nf.modalidade_frete = '0'
            nf.placa_veiculo = 'ABC1D23'
            nf.quantidade_volumes = 2
        nf.save()
        it = nf.itens.first()
        if long_desc:
            it.snapshot_produto = {**(it.snapshot_produto or {}), 'descricao': 'PRODUTO ' + ('LONGO ' * 30)}
        it.informacao_adicional_item = 'infAdProd HTML'
        it.save()
        base = nf.itens.first()
        for _ in range(extra):
            ItemNFeSaida.objects.create(
                nf=nf,
                produto=base.produto,
                quantidade=Decimal('1'),
                valor=Decimal('15'),
                snapshot_fiscal=base.snapshot_fiscal,
                snapshot_produto=base.snapshot_produto,
            )
        return nf

    def _gerar(self, nf: NFeSaida) -> tuple[bytes, dict, str]:
        dados = montar_dados_danfe_conferencia(nf)
        pdf, meta = render_danfe_conferencia_pdf(dados, nfe_saida_id=nf.pk)
        return pdf, meta, norm_pdf_text(pdf_text(pdf))

    def test_um_item_sem_erro(self):
        pdf, meta, t = self._gerar(self._nf())
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn('weasyprint', meta.get('render_engine', ''))

    def test_cinco_itens_sem_erro(self):
        pdf, _, t = self._gerar(self._nf(extra=4))
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn('84818200', t)

    def test_descricao_longa_transporte_inf_adicionais(self):
        pdf, _, t = self._gerar(self._nf(long_desc=True, transporte=True))
        self.assertIn('PRODUTO', t)
        self.assertIn('INFO COMPLEMENTAR', t)
        self.assertIn('INFADPROD', t)

    def test_conteudo_conferencia_obrigatorio(self):
        _, _, t = self._gerar(self._nf())
        c = compact_pdf_text(t)
        for trecho in (
            'DANFE',
            'NFECONFERENCIA',
            'SEMVALORFISCAL',
            'FALTAPROTOCOLODEAPROVACAODASEFAZ',
            'CONSULTADEAUTENTICIDADE',
            'WWNFEFAZENDAGOVBR',
            'RESERVADOAOFISCO',
        ):
            self.assertIn(compact_pdf_text(trecho), c, trecho)
        self.assertIn('CHAVEDEACESSO', c)
        self.assertIn('NAOGERADA', c)
        self.assertNotIn('NAOIMPRIMIRSECRETO', c)

    def test_nao_altera_status(self):
        nf = self._nf()
        st, sc = nf.status, nf.status_conferencia
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        self._gerar(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(nf.status_conferencia, sc)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)

    def test_api_preview(self):
        nf = self._nf()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
