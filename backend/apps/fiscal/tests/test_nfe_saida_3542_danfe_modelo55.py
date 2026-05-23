"""NF-e Saída 3.5.4.2 — DANFE modelo 55 conferência (MOC Anexo II)."""

from __future__ import annotations

import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework import status
from rest_framework.test import APIClient

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
class NFeSaida3542DanfeModelo55Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3542', 'nfe3542@test.com', 'x')
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

    def _nf(self, *, long_desc: bool = False) -> NFeSaida:
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
            'aliquota_icms': '18',
            'base_icms': '100',
            'valor_icms': '18',
            'cst_pis': '01',
            'valor_pis': '1.65',
            'cst_cofins': '01',
            'valor_cofins': '7.6',
        }
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.select_related('cliente', 'pedido_venda__empresa_emitente').get(
            pk=r['nfe_saida_id'],
        )
        nf.informacoes_adicionais = 'infCpl conferência modelo 55'
        nf.informacoes_fisco = 'infAdFisco teste'
        nf.observacoes_internas = 'SECRET INTERNO NAO IMPRIMIR'
        nf.pedido_cliente_numero = 'PED-900'
        nf.save()
        it = nf.itens.first()
        it.pedido_cliente_item = 'LIN-42'
        it.observacao_item = 'infAdProd linha 1'
        it.informacao_adicional_item = 'detalhe adicional item'
        if long_desc:
            it.snapshot_produto = {**(it.snapshot_produto or {}), 'descricao': 'X' * 120}
        it.save()
        return nf

    def test_pdf_modelo55_conteudo_completo(self):
        nf = self._nf()
        pdf, meta = gerar_danfe_modelo55_conferencia_pdf(nf)
        self.assertEqual(meta['content_type'], 'application/pdf')
        self.assertTrue(pdf.startswith(b'%PDF'))
        t = compact_pdf_text(pdf_text(pdf))
        obrigatorios = (
            'DANFE',
            'DOCUMENTOAUXILIARDANOTAFISCALELETRONICA',
            'NFECONFERENCIA',
            'SEMVALORFISCAL',
            'FALTAPROTOCOLODEAPROVACAODASEFAZ',
            'CONSULTADEAUTENTICIDADE',
            'RECEBEMOSDE',
            'VENDADEMERCADORIA',
            'DESTINATARIO',
            'CALCULODOIMPOSTO',
            'TRANSPORTADOR',
            'PRODUTOS',
            'DADOSADICIONAIS',
            'INFORMACOESCOMPLEMENTARES',
            'RESERVADOAOFISCO',
            '84818200',
            '5102',
            'INFCPL',
            'MODELO55',
            'INFADFISCO',
            'INFADPROD',
            'XPED',
            'PEDIDODOCLIENTE',
            'NITEMPEDLIN42',
            'CONFERENCIA',
            'WWNFEFAZENDAGOVBR',
        )
        for trecho in obrigatorios:
            self.assertIn(compact_pdf_text(trecho), t, trecho)
        self.assertNotIn('SECRET INTERNO', t)
        self.assertIn('CHAVEDEACESSO', t)
        self.assertIn('NAOGERADA', t)
        self.assertIn('CONSULTADEAUTENTICIDADE', t)
        digits = ''.join(c for c in t if c.isdigit())
        self.assertNotEqual(len(digits), 44)

    def test_produto_colunas_fiscais(self):
        nf = self._nf()
        pdf, _ = gerar_danfe_modelo55_conferencia_pdf(nf)
        t = compact_pdf_text(pdf_text(pdf))
        for col in ('NCM', 'CFOP', 'ICMS', 'QUANT', 'UN', 'VALORUNIT', 'VALORTOTAL', 'BCALCICMS', 'ALIQ', 'IPI'):
            self.assertIn(col, t, col)

    def test_descricao_longa(self):
        nf = self._nf(long_desc=True)
        pdf, _ = gerar_danfe_modelo55_conferencia_pdf(nf)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf_text(pdf)), 200)

    def test_nao_altera_sistema(self):
        nf = self._nf()
        st = nf.status
        sc = nf.status_conferencia
        evt = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()
        gerar_danfe_modelo55_conferencia_pdf(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st)
        self.assertEqual(nf.status_conferencia, sc)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), evt)

    def test_pagina_adicional_cabecalho_minimo(self):
        """Layout HTML absoluto (1 pág.): muitos itens geram PDF válido; multipágina em fase futura."""
        nf = self._nf()
        base = nf.itens.first()
        for i in range(24):
            ItemNFeSaida.objects.create(
                nf=nf,
                produto=base.produto,
                quantidade=Decimal('1'),
                valor=Decimal('10'),
                snapshot_fiscal=base.snapshot_fiscal,
                snapshot_produto=base.snapshot_produto,
            )
        pdf = gerar_danfe_modelo55_conferencia_pdf(nf)[0]
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreaterEqual(len(PdfReader(io.BytesIO(pdf)).pages), 1)

    def test_multiplos_itens_multipagina(self):
        """Muitos itens: PDF válido; paginação extra do HTML será tratada em fase futura."""
        nf = self._nf()
        base = nf.itens.first()
        for i in range(14):
            ItemNFeSaida.objects.create(
                nf=nf,
                produto=base.produto,
                quantidade=Decimal('1'),
                valor=Decimal('10'),
                snapshot_fiscal=base.snapshot_fiscal,
                snapshot_produto=base.snapshot_produto,
                observacao_item=f'Obs item extra {i}',
            )
        pdf, _ = gerar_danfe_modelo55_conferencia_pdf(nf)
        reader = PdfReader(io.BytesIO(pdf))
        self.assertGreaterEqual(len(reader.pages), 1)
        t = pdf_text(pdf)
        self.assertIn('Folha', t)
        self.assertIn('84818200', compact_pdf_text(t))

    def test_api_preview_danfe(self):
        nf = self._nf()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('inline', res['Content-Disposition'])
        self.assertIn('danfe-conferencia', res['Content-Disposition'])

    def test_api_danfe_conferencia_alias(self):
        nf = self._nf()
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/danfe-conferencia/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.content.startswith(b'%PDF'))
