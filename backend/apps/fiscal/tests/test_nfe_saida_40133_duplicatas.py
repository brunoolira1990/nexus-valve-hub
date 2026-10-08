"""ERP 4.0.13.3 — Duplicatas no XML/DANFE da NF-e Saída (sem financeiro automático)."""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.comercial.faturamento_pedido_venda import montar_resumo_faturamento
from apps.comercial.payment_terms import compute_due_dates
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.danfe_render import render_danfe_conferencia_pdf
from apps.fiscal.models import EstoqueCorrida, NFeSaida
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_integracao.nfe_xml_preliminar import gerar_resultado_xml_preliminar
from apps.fiscal.nfe_saida_duplicatas import (
    aplicar_duplicatas_nfe_saida,
    gerar_duplicatas_nfe_saida,
)
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.tests.test_nfe_saida_354_danfe_conferencia import _regra
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _ensure_numeracao_empresa


def _fiscal_snapshot_item(item) -> None:
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


def _pedido_com_prazo(
    *,
    valor: Decimal = Decimal('5000'),
    dias: int = 45,
    qtd: Decimal = Decimal('50'),
    preco: Decimal = Decimal('100'),
):
    pedido, item = _pedido_item(qtd=qtd, preco=preco)
    pedido.valor_total = valor
    pedido.condicao_pagamento_texto = f'{dias} DDL'
    pedido.dias_parcelas = [dias]
    pedido.quantidade_parcelas = 1
    venc = compute_due_dates(pedido.data, [dias])[0]
    pedido.vencimentos_previstos = [venc]
    pedido.save(
        update_fields=[
            'valor_total',
            'condicao_pagamento_texto',
            'dias_parcelas',
            'quantidade_parcelas',
            'vencimentos_previstos',
        ],
    )
    return pedido, item, venc


def _pedido_multi_parcelas():
    pedido, item = _pedido_item(qtd=Decimal('3'), preco=Decimal('100'))
    pedido.valor_total = Decimal('300')
    pedido.condicao_pagamento_texto = '30/60/90'
    pedido.dias_parcelas = [30, 60, 90]
    pedido.quantidade_parcelas = 3
    pedido.vencimentos_previstos = compute_due_dates(pedido.data, [30, 60, 90])
    pedido.save(
        update_fields=[
            'valor_total',
            'condicao_pagamento_texto',
            'dias_parcelas',
            'quantidade_parcelas',
            'vencimentos_previstos',
        ],
    )
    return pedido, item


def _nf_com_prazo() -> tuple[NFeSaida, date]:
    pedido, item, venc = _pedido_com_prazo()
    _fiscal_snapshot_item(item)
    _ensure_numeracao_empresa(pedido.empresa_emitente)
    emp = pedido.empresa_emitente
    if not emp.ie:
        emp.ie = '123456789012'
        emp.save(update_fields=['ie'])
    fat = _faturamento_pronto(pedido, item, qtd='50')
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
    return nf, venc


def _xml_tem_tag(xml: str, tag: str) -> bool:
    return bool(re.search(rf'<[\w:]*{re.escape(tag)}\b', xml, flags=re.IGNORECASE))


@override_settings(
    USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True,
    FISCAL_PERSISTIR_XML_PRELIMINAR=True,
)
class NFeSaida40133DuplicatasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username=f'dup_{uuid.uuid4().hex[:8]}',
            password='test123',
        )
        _regra()

    def test_uma_parcela_gera_duplicata_001(self):
        nf, _ = _nf_com_prazo()
        dups = gerar_duplicatas_nfe_saida(nf)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]['numero'], '001')

    def test_vencimento_e_valor_corretos(self):
        nf, venc = _nf_com_prazo()
        dups = gerar_duplicatas_nfe_saida(nf)
        self.assertEqual(dups[0]['vencimento'], venc.isoformat())
        self.assertEqual(dups[0]['valor'], Decimal('5000.00'))

    def test_soma_duplicatas_bate_total_nf(self):
        nf, _ = _nf_com_prazo()
        dups = gerar_duplicatas_nfe_saida(nf)
        total = sum(d['valor'] for d in dups)
        self.assertEqual(total, nf.valor_total)

    def test_multiplas_parcelas_numeracao_e_arredondamento(self):
        pedido, item = _pedido_multi_parcelas()
        fat = _faturamento_pronto(pedido, item, qtd='3')
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        dups = gerar_duplicatas_nfe_saida(nf)
        self.assertEqual([d['numero'] for d in dups], ['001', '002', '003'])
        self.assertEqual(sum(d['valor'] for d in dups), nf.valor_total)
        self.assertEqual(dups[-1]['valor'], Decimal('100.00'))

    def test_nao_gera_duplicata_zerada(self):
        nf, _ = _nf_com_prazo()
        dups = gerar_duplicatas_nfe_saida(nf)
        self.assertTrue(all(d['valor'] > 0 for d in dups))

    @staticmethod
    def _skip_sem_nfelib():
        if not nfelib_disponivel():
            return True
        return False

    def test_xml_contem_cobr_dup_quando_prazo(self):
        if self._skip_sem_nfelib():
            self.skipTest('nfelib indisponível')
        nf, venc = _nf_com_prazo()
        nf.refresh_from_db()
        venc_dup = nf.titulos_receber[0]['vencimento']
        xml = gerar_resultado_xml_preliminar(nf)['xml']
        self.assertTrue(_xml_tem_tag(xml, 'cobr'))
        self.assertTrue(_xml_tem_tag(xml, 'fat'))
        self.assertTrue(_xml_tem_tag(xml, 'dup'))
        self.assertIn(f'<dVenc>{venc_dup}</dVenc>', xml.replace('ns0:', ''))
        self.assertIn('<nDup>001</nDup>', xml.replace('ns0:', ''))

    def test_xml_pag_a_prazo_usa_boleto(self):
        if self._skip_sem_nfelib():
            self.skipTest('nfelib indisponível')
        nf, _ = _nf_com_prazo()
        xml = gerar_resultado_xml_preliminar(nf)['xml']
        self.assertIn('<tPag>15</tPag>', xml.replace('ns0:', ''))

    def test_aplicar_duplicatas_nao_altera_estoque(self):
        antes = EstoqueCorrida.objects.count()
        nf, _ = _nf_com_prazo()
        aplicar_duplicatas_nfe_saida(nf)
        self.assertEqual(EstoqueCorrida.objects.count(), antes)

    def test_api_expose_duplicatas_nfe(self):
        nf, venc = _nf_com_prazo()
        data = NFeSaidaSerializer(nf).data
        self.assertIn('duplicatas_nfe', data)
        self.assertEqual(len(data['duplicatas_nfe']), 1)
        dup = data['duplicatas_nfe'][0]
        self.assertEqual(dup['numero'], '001')
        self.assertEqual(dup['vencimento'], venc.isoformat())
        self.assertIn('valor_formatado', dup)

    def test_resumo_faturamento_expose_duplicatas(self):
        nf, venc = _nf_com_prazo()
        resumo = montar_resumo_faturamento(nf.pedido_venda)
        linha = next(f for f in resumo['faturamentos_nfe'] if f['nfe_saida_id'] == nf.pk)
        self.assertEqual(len(linha['duplicatas_nfe']), 1)
        self.assertEqual(linha['duplicatas_nfe'][0]['numero'], '001')
        self.assertEqual(linha['duplicatas_nfe'][0]['vencimento'], venc.isoformat())

    def test_danfe_contem_duplicatas(self):
        nf, venc = _nf_com_prazo()
        dados = montar_dados_danfe_conferencia(nf)
        self.assertEqual(len(dados['duplicatas']), 1)
        self.assertEqual(dados['duplicatas'][0]['numero'], '001')
        self.assertEqual(dados['duplicatas'][0]['vencimento'], venc.strftime('%d/%m/%Y'))
        self.assertIn('5.000,00', dados['duplicatas'][0]['valor'])

        pdf, _ = render_danfe_conferencia_pdf(dados, nfe_saida_id=nf.pk)
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('001', texto)
        self.assertIn(venc.strftime('%d/%m/%Y').replace('/', ''), texto.replace('/', ''))
        self.assertIn('5000', texto.replace('.', '').replace(',', ''))

    def test_pdf_comercial_pedido_sem_duplicatas_fiscais(self):
        pedido, _, _ = _pedido_com_prazo()
        pdf = gerar_pedido_venda_pdf_bytes(pedido)
        texto = pdf.decode('latin-1', errors='ignore').lower()
        self.assertNotIn('duplicatas da nf-e', texto)
        self.assertNotIn('danfe', texto)
        self.assertNotIn('<cobr>', texto)

    def test_a_vista_nao_gera_duplicata(self):
        pedido, item = _pedido_item()
        pedido.condicao_pagamento_texto = 'à vista'
        pedido.dias_parcelas = [0]
        pedido.quantidade_parcelas = 1
        pedido.vencimentos_previstos = compute_due_dates(pedido.data, [0])
        pedido.save(
            update_fields=[
                'condicao_pagamento_texto',
                'dias_parcelas',
                'quantidade_parcelas',
                'vencimentos_previstos',
            ],
        )
        fat = _faturamento_pronto(pedido, item)
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        self.assertEqual(gerar_duplicatas_nfe_saida(nf), [])

    def test_validar_conferencia_recalcula_vencimentos_por_data_emissao(self):
        from apps.fiscal.nfe_saida_prontidao import validar_conferencia_nfe

        pedido, item = _pedido_multi_parcelas()
        pedido.data = date(2026, 1, 1)
        pedido.vencimentos_previstos = compute_due_dates(pedido.data, [30, 60, 90])
        pedido.save(update_fields=['data', 'vencimentos_previstos'])

        _fiscal_snapshot_item(item)
        _ensure_numeracao_empresa(pedido.empresa_emitente)
        fat = _faturamento_pronto(pedido, item, qtd='3')
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])

        emissao = date(2026, 6, 24)
        nf.data = emissao
        nf.vencimentos_finais = list(pedido.vencimentos_previstos)
        nf.save(update_fields=['data', 'vencimentos_finais'])

        vencimentos_antigos = [v.isoformat() for v in pedido.vencimentos_previstos]
        self.assertEqual([t['vencimento'] for t in nf.titulos_receber], vencimentos_antigos)

        resultado = validar_conferencia_nfe(nf, usuario=self.user)
        nf.refresh_from_db()

        esperados = [d.isoformat() for d in compute_due_dates(emissao, [30, 60, 90])]
        self.assertEqual([t['vencimento'] for t in nf.titulos_receber], esperados)
        self.assertEqual(
            [d['vencimento'] for d in resultado['conferencia']['nfe']['duplicatas_nfe']],
            esperados,
        )
