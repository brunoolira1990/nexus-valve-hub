"""NF-e 3.5.4.6 — DANFE Conferência: paginação (1 item = 1 página via endpoint real)."""

from __future__ import annotations

import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from pypdf import PdfReader
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.danfe_render import RENDERER_HTML
from apps.fiscal.models import ItemNFeSaida, NFeSaida, NFeSaidaEvento
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


def _nf_um_item() -> NFeSaida:
    pedido, item = _pedido_item()
    item.snapshot_fiscal = {
        'ncm': '84818200',
        'cfop': '5102',
        'cst_icms': '00',
        'aliquota_icms': '18',
        'cst_pis': '01',
        'valor_pis': '1',
        'cst_cofins': '01',
        'valor_cofins': '2',
    }
    item.save(update_fields=['snapshot_fiscal'])
    fat = _faturamento_pronto(pedido, item)
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    nf = NFeSaida.objects.select_related('cliente', 'pedido_venda__empresa_emitente').get(
        pk=r['nfe_saida_id'],
    )
    nf.informacoes_adicionais = 'Info complementar paginacao DANFE'
    nf.informacoes_fisco = 'Reservado fisco paginacao'
    nf.save(update_fields=['informacoes_adicionais', 'informacoes_fisco'])
    self_assert = ItemNFeSaida.objects.filter(nf=nf).count()
    if self_assert != 1:
        raise AssertionError(f'Esperado 1 item na NF-e, obteve {self_assert}')
    return nf


@override_settings(
    USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True,
    FISCAL_DANFE_RENDERER=RENDERER_HTML,
)
class NFeSaida3546DanfePaginacaoTests(TestCase):
    """Caminho real da API (mesmo do navegador) — WeasyPrint HTML."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3546', 'nfe3546@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        _regra()

    def _pdf_endpoint(self, nf: NFeSaida, path_suffix: str) -> bytes:
        res = self.client.get(f'/api/nf-saidas/{nf.pk}/{path_suffix}')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content[:200])
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'), 'resposta deve ser PDF')
        return res.content

    def test_danfe_conferencia_um_item_uma_pagina(self):
        nf = _nf_um_item()
        status_antes = nf.status
        conf_antes = nf.status_conferencia
        eventos_antes = NFeSaidaEvento.objects.filter(nfe_saida=nf).count()

        pdf = self._pdf_endpoint(nf, 'danfe-conferencia/')
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1, 'NF-e com 1 item deve gerar exatamente 1 página')

        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('DANFE', texto)
        self.assertIn('NFECONFERENCIA', texto)
        self.assertIn('SEMVALORFISCAL', texto)
        self.assertIn('FALTAPROTOCOLODEAPROVACAODASEFAZ', texto)
        self.assertIn('DADOSDOSPRODUTOS', texto)
        self.assertIn('DADOSADICIONAIS', texto)
        self.assertIn('INFOCOMPLEMENTARPAGINACAODANFE', texto)
        self.assertIn('NAOGERADA', texto)

        nf.refresh_from_db()
        self.assertEqual(nf.status, status_antes)
        self.assertEqual(nf.status_conferencia, conf_antes)
        self.assertEqual(NFeSaidaEvento.objects.filter(nfe_saida=nf).count(), eventos_antes)

    def test_preview_danfe_mesmo_renderer_e_uma_pagina(self):
        nf = _nf_um_item()
        pdf = self._pdf_endpoint(nf, 'preview-danfe/')
        self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages), 1)

    def test_cinco_itens_pode_uma_pagina_se_couber(self):
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00', 'aliquota_icms': '18'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        base = ItemNFeSaida.objects.filter(nf=nf).first()
        for i in range(4):
            ItemNFeSaida.objects.create(
                nf=nf,
                produto=base.produto,
                quantidade=Decimal('1'),
                valor=Decimal('10'),
                snapshot_fiscal=base.snapshot_fiscal,
                snapshot_produto=base.snapshot_produto,
            )
        self.assertEqual(ItemNFeSaida.objects.filter(nf=nf).count(), 5)
        pdf = self._pdf_endpoint(nf, 'danfe-conferencia/')
        pages = len(PdfReader(io.BytesIO(pdf)).pages)
        self.assertLessEqual(pages, 2, '5 itens compactos devem caber em no máximo 2 páginas')
        self.assertGreaterEqual(pages, 1)
