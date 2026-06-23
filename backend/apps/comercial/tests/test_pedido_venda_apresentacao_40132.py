"""ERP 4.0.13.2.1 — apresentação amigável NF-e/faturamento no PDF do pedido."""

from __future__ import annotations

import io

from django.test import TestCase
from pypdf import PdfReader

from apps.comercial.pedido_venda_apresentacao import (
    condicao_pagamento_pdf_amigavel,
    formatar_identidade_nfe_pedido,
    label_faturamento_status,
    linha_faturamento_pdf,
    prazo_entrega_pdf_amigavel,
    titulo_secao_nfe_pdf,
)
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.tests.test_comercial_pdf_proposta_pedido import ComercialPdfBaseFixture
from apps.comercial.models import FaturamentoPedidoVenda
from apps.fiscal.models import NFeSaida


def _pdf_text(pdf_bytes: bytes) -> str:
    text = ''
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        text += page.extract_text() or ''
    return text


class PedidoVendaApresentacaoHelperTests(TestCase):
    def test_homolog_titulo_e_badges(self):
        linha = {
            'faturamento_id': 2,
            'nfe_saida_id': 9,
            'nfe_saida_numero': 'RASCUNHO-FAT-2',
            'nfe_saida_status': 'AUTORIZADA_HOMOLOGACAO',
            'nfe_status_emissao_sefaz': 'AUTORIZADA_HOMOLOGACAO',
            'nfe_titulo_exibicao': 'NF-e Homologação nº 000000002 — Série 0',
            'nfe_numero_fiscal': '000000002',
            'nfe_serie_fiscal': '0',
            'nfe_cstat': '100',
            'status': 'GERADO_NFE',
        }
        idn = formatar_identidade_nfe_pedido(linha)
        self.assertIn('NF-e Homologação', idn['titulo'])
        self.assertNotIn('rascunho', idn['titulo'].lower())
        self.assertEqual(idn['referencia_interna'], 'RASCUNHO-FAT-2')
        self.assertIn('Sem valor fiscal', idn['badges'])
        self.assertEqual(label_faturamento_status('GERADO_NFE'), 'NF-e gerada')

    def test_inconsistencia_gerado_sem_nfe(self):
        linha = {'faturamento_id': 1, 'status': 'GERADO_NFE', 'nfe_saida_id': None}
        rotulo, valor = linha_faturamento_pdf(linha)
        self.assertIn('vínculo não localizado', valor)
        self.assertNotIn('GERADO_NFE', valor)

    def test_condicao_pagamento_dias(self):
        self.assertEqual(condicao_pagamento_pdf_amigavel('45', []), '45 dias')

    def test_prazo_uteis(self):
        self.assertIn('úteis', prazo_entrega_pdf_amigavel('7 dias Uteis'))

    def test_titulo_secao_autorizada(self):
        linhas = [
            {
                'nfe_saida_id': 1,
                'nfe_status_emissao_sefaz': 'AUTORIZADA_HOMOLOGACAO',
                'nfe_saida_status': 'AUTORIZADA_HOMOLOGACAO',
            }
        ]
        self.assertEqual(titulo_secao_nfe_pdf(linhas), 'NF-e vinculada')


class PedidoVendaPdfApresentacao40132Tests(ComercialPdfBaseFixture):
    def test_pdf_comercial_sem_secao_nfe_fiscal(self):
        from apps.comercial.serializers import PedidoVendaSerializer
        from apps.comercial.faturamento_pedido_venda import (
            confirmar_faturamento_pedido,
            criar_faturamento_pedido,
        )

        ser = PedidoVendaSerializer(
            data={
                'empresa_emitente_id': self.empresa.id,
                'cliente_id': self.cliente.id,
                'data': '2026-05-21',
                'status': 'ABERTO',
                'condicao_pagamento_texto': '45',
                'prazo_entrega_texto': '7 dias Uteis',
                'itens': [
                    {
                        'produto_id': self.prod.id,
                        'quantidade': '10',
                        'quantidade_negociada': '10',
                        'valor_unitario': '500',
                        'preco_por_unidade_negociada': '500',
                        'unidade_negociada': 'PC',
                    }
                ],
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pedido = ser.save()
        item = pedido.itens.first()
        criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.pk, 'quantidade': '10'}]},
        )
        fat = pedido.faturamentos.filter(status=FaturamentoPedidoVenda.Status.RASCUNHO).first()
        confirmar_faturamento_pedido(pedido, fat.pk)
        fat.refresh_from_db()
        fat.status = FaturamentoPedidoVenda.Status.GERADO_NFE
        nfe = NFeSaida.objects.create(
            numero='RASCUNHO-FAT-2',
            status='AUTORIZADA_HOMOLOGACAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            numero_nfe='2',
            serie_nfe='0',
            cstat_autorizacao='100',
            cliente=self.cliente,
            data='2026-05-21',
            faturamento_pedido_venda=fat,
            pedido_venda=pedido,
        )
        fat.nfe_saida = nfe
        fat.save(update_fields=['status', 'nfe_saida'])

        text = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertIn('Valor faturado', text)
        self.assertIn('Valor faturado', text)
        self.assertIn('45 dias', text)
        self.assertIn('úteis', text.lower())
        self.assertNotIn('NF-e vinculada', text)
        self.assertNotIn('NF-e vinculadas', text)
        self.assertNotIn('Homologação', text)
        self.assertNotIn('cStat', text)
        self.assertNotIn('RASCUNHO-FAT', text)
        self.assertNotIn('AUTORIZADA_HOMOLOGACAO', text)
        self.assertNotIn('GERADO_NFE', text)
        self.assertNotIn('Sem valor fiscal', text)
        self.assertNotIn('Fora da apuração', text)
