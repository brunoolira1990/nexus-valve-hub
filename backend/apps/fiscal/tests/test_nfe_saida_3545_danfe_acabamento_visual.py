"""NF-e 3.5.4.5 — Acabamento visual DANFE Conferência HTML/CSS."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.danfe_render import render_danfe_conferencia_pdf
from apps.fiscal.models import ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeSaida3545DanfeAcabamentoVisualTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3545', 'nfe3545@test.com', 'x')
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
        }
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        nf.informacoes_adicionais = 'Info complementar acabamento 3545'
        nf.informacoes_fisco = 'Reservado fisco 3545'
        nf.observacoes_internas = 'OBS INTERNA NAO PDF'
        if transporte:
            nf.modalidade_frete = '0'
            nf.valor_frete = Decimal('25')
            nf.quantidade_volumes = 3
            nf.peso_bruto = Decimal('12')
        nf.save()
        it = nf.itens.first()
        if long_desc:
            it.snapshot_produto = {**(it.snapshot_produto or {}), 'descricao': 'ITEM ' + ('LONGO ' * 25)}
        it.informacao_adicional_item = 'infAdProd 3545'
        it.save()
        base = nf.itens.first()
        for _ in range(extra):
            ItemNFeSaida.objects.create(
                nf=nf,
                produto=base.produto,
                quantidade=Decimal('1'),
                valor=Decimal('20'),
                snapshot_fiscal=base.snapshot_fiscal,
                snapshot_produto=base.snapshot_produto,
            )
        return nf

    def _pdf_compact(self, nf: NFeSaida) -> str:
        dados = montar_dados_danfe_conferencia(nf)
        pdf, _ = render_danfe_conferencia_pdf(dados, nfe_saida_id=nf.pk)
        self.assertTrue(pdf.startswith(b'%PDF'))
        return compact_pdf_text(pdf_text(pdf))

    def test_um_item_gera_sem_erro(self):
        self.assertGreater(len(self._pdf_compact(self._nf())), 200)

    def test_cinco_itens_gera_sem_erro(self):
        c = self._pdf_compact(self._nf(extra=4))
        self.assertIn('84818200', c)

    def test_descricao_longa_transporte_inf_adicionais(self):
        c = self._pdf_compact(self._nf(long_desc=True, transporte=True, extra=0))
        self.assertIn('VALORFRETE', c)
        self.assertIn('PESOBRUTO', c)
        self.assertIn('INFOCOMPLEMENTARACABAMENTO3545', c)
        self.assertIn('RESERVADOAOFISCO', c)
        self.assertIn('RESERVADOFISCO3545', c)
        self.assertIn('INFADPROD3545', c)
        self.assertNotIn('OBSINTERNANOPDF', c)

    def test_area_reservada_sem_fake(self):
        c = self._pdf_compact(self._nf())
        self.assertIn('CHAVEDEACESSO', c)
        self.assertTrue(
            'NAOGERADA' in c or 'CHAVEPRELIMINAR' in c or 'PENDENTE' in c,
            'mensagem de chave pendente/preliminar',
        )
        self.assertIn('CONSULTADEAUTENTICIDADE', c)
        self.assertIn('WWNFEFAZENDAGOVBR', c)
        digits = ''.join(x for x in c if x.isdigit())
        self.assertNotEqual(len(digits), 44)

    def test_nao_altera_status(self):
        nf = self._nf()
        st, sc = nf.status, nf.status_conferencia
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        self._pdf_compact(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(nf.status_conferencia, sc)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)
