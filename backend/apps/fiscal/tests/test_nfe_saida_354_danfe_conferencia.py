"""NF-e Saída 3.5.4 — DANFE de conferência em layout real."""

from __future__ import annotations

import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from pypdf import PdfReader
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.danfe_conferencia import gerar_danfe_conferencia_pdf, montar_dados_danfe_conferencia
from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _regra() -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm='84818200',
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'Venda SP',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
        },
    )
    return regra


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeSaida354DanfeConferenciaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe354', 'nfe354@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        _regra()

    def _nf(self) -> NFeSaida:
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
            'aliquota_icms': '18',
            'valor_icms': '18',
            'cst_pis': '01',
            'valor_pis': '1',
            'cst_cofins': '01',
            'valor_cofins': '2',
        }
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.select_related('cliente', 'transportadora', 'pedido_venda__empresa_emitente').get(
            pk=r['nfe_saida_id'],
        )
        nf.informacoes_adicionais = 'Info complementar DANFE'
        nf.informacoes_fisco = 'Texto reservado fisco'
        nf.observacoes_internas = 'NÃO DEVE APARECER NO PDF'
        nf.pedido_cliente_numero = 'PC-5050'
        nf.modalidade_frete = '0'
        nf.valor_frete = Decimal('50')
        nf.quantidade_volumes = 2
        nf.peso_bruto = Decimal('10')
        nf.peso_liquido = Decimal('9')
        nf.save()
        return nf

    def test_endpoint_preview_danfe_pdf(self):
        nf = self._nf()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_endpoint_danfe_conferencia_alias(self):
        nf = self._nf()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/danfe-conferencia/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('danfe-conferencia', res['Content-Disposition'])

    def test_pdf_conteudo_obrigatorio(self):
        nf = self._nf()
        pdf, _ = gerar_danfe_conferencia_pdf(nf)
        c = compact_pdf_text(pdf_text(pdf))
        self.assertTrue(pdf.startswith(b'%PDF'))
        for trecho in (
            'DANFE',
            'DOCUMENTOAUXILIAR',
            'SEMVALORFISCAL',
            'SEMPROTOCOLO',
            'NAOAUTORIZADA',
            'RECEBEMOSDE',
            'NCM',
            'CFOP',
            'ICMS',
            'IMPOSTO',
            'INFOCOMPLEMENTARDANFE',
            'PC5050',
            'RESERVADOAOFISCO',
            'TEXTORESERVADOFISCO',
        ):
            self.assertIn(compact_pdf_text(trecho), c, trecho)
        self.assertNotIn('NAODEVEAPARECER', c)

    def test_chave_nao_gerada_em_rascunho(self):
        nf = self._nf()
        dados = montar_dados_danfe_conferencia(nf)
        self.assertIn('NÃO GERADA', dados['chave_display'].upper())

    def test_gerar_nao_altera_status_nem_eventos_sefaz(self):
        nf = self._nf()
        st_antes = nf.status
        evt_antes = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        gerar_danfe_conferencia_pdf(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st_antes)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt_antes)

    def test_multiplos_itens_sem_erro(self):
        nf = self._nf()
        item = nf.itens.first()
        from apps.fiscal.models import ItemNFeSaida

        ItemNFeSaida.objects.create(
            nf=nf,
            produto=item.produto,
            quantidade=Decimal('2'),
            valor=Decimal('100'),
            snapshot_fiscal=item.snapshot_fiscal,
            snapshot_produto=item.snapshot_produto,
        )
        pdf, _ = gerar_danfe_conferencia_pdf(nf)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(PdfReader(io.BytesIO(pdf)).pages), 0)
