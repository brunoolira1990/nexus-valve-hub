"""Layout compacto do PDF do Pedido de Venda — paginação e rodapé."""

from __future__ import annotations

import io
import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase
from pypdf import PdfReader

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(suf: str) -> Produto:
    u = uuid.uuid4().hex[:4].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'L{u}{suf}'[:12],
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Item layout {suf}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PV-LAY-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_com_itens(qtd_itens: int) -> PedidoVenda:
    emp = Empresa.objects.create(razao_social='Emit Layout', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli Layout', cnpj=_cnpj(), uf='SP')
    pedido = PedidoVenda.objects.create(
        numero=f'PV-LAY-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        vendedor='Vendedor Layout',
        condicao_pagamento_texto='30',
        valor_total=Decimal(str(100 * qtd_itens)),
    )
    for i in range(qtd_itens):
        ItemPedidoVenda.objects.create(
            pedido=pedido,
            produto=_produto(f'{i:02d}'),
            quantidade=Decimal('1'),
            valor_unitario=Decimal('100'),
            unidade_negociada='PC',
        )
    return pedido


def _page_count(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


def _pdf_text(pdf_bytes: bytes) -> str:
    return ''.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


class PedidoVendaPdfLayoutTests(TestCase):
    def test_pdf_poucos_itens_cabe_em_uma_pagina(self):
        for n in (1, 2, 3):
            with self.subTest(itens=n):
                pedido = _pedido_com_itens(n)
                pages = _page_count(gerar_pedido_venda_pdf_bytes(pedido))
                self.assertEqual(pages, 1, f'esperado 1 página com {n} item(ns), obtido {pages}')

    def test_pdf_totais_na_mesma_pagina_dos_itens(self):
        pedido = _pedido_com_itens(2)
        reader = PdfReader(io.BytesIO(gerar_pedido_venda_pdf_bytes(pedido)))
        self.assertEqual(len(reader.pages), 1)
        texto = reader.pages[0].extract_text() or ''
        self.assertIn('VALOR TOTAL FINAL', texto.replace('\n', ' ').upper())

    def test_pdf_muitos_itens_pagina_corretamente(self):
        pedido = _pedido_com_itens(18)
        pages = _page_count(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertGreaterEqual(pages, 2, 'pedido extenso deve usar mais de uma página')

    def test_pdf_preserva_campos_faturamento_no_bloco_condicoes(self):
        pedido = _pedido_com_itens(1)
        texto = _pdf_text(gerar_pedido_venda_pdf_bytes(pedido))
        self.assertIn('Valor faturado', texto)
        self.assertIn('faturamento', texto.lower())
        self.assertIn('Qtd. pedida', texto)
