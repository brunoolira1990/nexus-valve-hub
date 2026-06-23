"""PDF comercial Pedido de Venda — totais derivados dos itens (ERP 4.0.13.6.1)."""

from __future__ import annotations

import io
import re
import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase
from pypdf import PdfReader

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import (
    confirmar_faturamento_pedido,
    criar_faturamento_pedido,
    montar_resumo_faturamento,
)
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.pedido_venda_totais import calcular_totais_pedido_venda
from apps.fiscal.models import NFeSaida
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _pedido_stale_total(*, qtd=Decimal('2'), preco=Decimal('250'), valor_salvo=Decimal('250')):
    emp = Empresa.objects.create(razao_social='Emit PDF', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli PDF', cnpj=_cnpj(), uf='RJ')
    fam = FamiliaProduto.objects.create(
        codigo_figura='FPDF',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao='FLANGE SW ACO CARBONO ANSI 150# RF SCH 160 1.1/2"',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo='00000030',
        unidade='PC',
        ncm='73079100',
    )
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:8]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='Aberto',
        valor_total=valor_salvo,
    )
    ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=qtd,
        quantidade_negociada=qtd,
        valor_unitario=preco,
        preco_por_unidade_negociada=preco,
        desconto=Decimal('0'),
        unidade_negociada='PC',
    )
    return pedido


def _pdf_text(pdf_bytes: bytes) -> str:
    text = ''
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        text += page.extract_text() or ''
    return text


def _norm_money(s: str) -> str:
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


class PedidoVendaPdfTotaisTests(TestCase):
    def test_calcular_totais_2x250_500_mesmo_com_salvo_250(self):
        pedido = _pedido_stale_total(valor_salvo=Decimal('250'))
        tot = calcular_totais_pedido_venda(pedido)
        self.assertEqual(tot.subtotal_produtos, Decimal('500.00'))
        self.assertEqual(tot.valor_total, Decimal('500.00'))
        self.assertEqual(tot.valor_total_salvo, Decimal('250.00'))
        self.assertTrue(tot.divergente_salvo)

    def test_pdf_mostra_total_500_nao_250(self):
        pedido = _pedido_stale_total(valor_salvo=Decimal('250'))
        text = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertIn('500,00', text)
        self.assertIn('Subtotal produtos', text)
        self.assertIn('VALOR TOTAL FINAL', text)
        self.assertIn('Valor total', text)
        self.assertIn('pedido:', text.replace('\n', ' '))
        self.assertIn('Valor pendente', text)
        self.assertIn('Valor faturado', text)
        # Não deve usar unitário como total final
        idx_total_final = text.find('VALOR TOTAL FINAL')
        self.assertGreater(idx_total_final, 0)
        trecho_final = text[idx_total_final : idx_total_final + 80]
        self.assertIn('500,00', trecho_final)
        self.assertNotIn('250,00', trecho_final.split('VALOR TOTAL FINAL', 1)[-1][:60])

    def test_resumo_faturamento_usa_total_recalculado(self):
        pedido = _pedido_stale_total(valor_salvo=Decimal('250'))
        resumo = montar_resumo_faturamento(pedido)
        self.assertEqual(resumo['valor_total_pedido'], '500.00')
        self.assertEqual(resumo['valor_faturado'], '0.00')
        self.assertEqual(resumo['valor_pendente'], '500.00')
        self.assertTrue(resumo['valor_total_recalculado'])
        self.assertTrue(any(i['codigo'] == 'valor_total_pedido_desatualizado' for i in resumo['inconsistencias']))
        self.assertFalse(resumo['tem_inconsistencia_bloqueante_nfe'])

    def test_pdf_faturado_parcial_coerente(self):
        pedido = _pedido_stale_total(valor_salvo=Decimal('250'))
        item = pedido.itens.first()
        criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '1'}]})
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        text = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertIn('250,00', text)
        resumo = montar_resumo_faturamento(pedido)
        self.assertEqual(resumo['valor_faturado'], '250.00')
        self.assertEqual(resumo['valor_pendente'], '250.00')

    def test_pdf_sem_secao_nfe_vinculada(self):
        pedido = _pedido_stale_total(valor_salvo=Decimal('250'))
        text = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertNotIn('NF-e vinculada', text)
        self.assertNotIn('DANFE', text)

    def test_pdf_nao_gera_nfe_financeiro(self):
        pedido = _pedido_stale_total(valor_salvo=Decimal('250'))
        nfe_antes = NFeSaida.objects.count()
        gerar_pedido_venda_pdf_bytes(pedido)
        self.assertEqual(NFeSaida.objects.count(), nfe_antes)
