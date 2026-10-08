"""Ordem de inclusão de itens em pedido de venda e NF-e saída."""

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
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(desc: str, codigo: str) -> Produto:
    suf = uuid.uuid4().hex[:4].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'O{suf}',
        descricao_base='F',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=desc,
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=codigo,
        unidade='PC',
        ncm='84818200',
    )


class OrdenacaoItensInclusaoTests(TestCase):
    def test_pedido_itens_por_id_asc(self):
        emp = Empresa.objects.create(razao_social='E', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='C', cnpj=_cnpj(), uf='SP')
        pedido = PedidoVenda.objects.create(
            numero='PV-ORD',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('300'),
        )
        p_c = _produto('Item C', 'COD-C')
        p_a = _produto('Item A', 'COD-A')
        p_b = _produto('Item B', 'COD-B')
        ItemPedidoVenda.objects.create(
            pedido=pedido, produto=p_c, quantidade=Decimal('1'), valor_unitario=Decimal('100'),
        )
        ItemPedidoVenda.objects.create(
            pedido=pedido, produto=p_a, quantidade=Decimal('1'), valor_unitario=Decimal('100'),
        )
        ItemPedidoVenda.objects.create(
            pedido=pedido, produto=p_b, quantidade=Decimal('1'), valor_unitario=Decimal('100'),
        )
        descricoes = [it.produto.descricao for it in pedido.itens.all()]
        self.assertEqual(descricoes, ['Item C', 'Item A', 'Item B'])

    def test_nfe_saida_itens_por_id_asc(self):
        cli = Cliente.objects.create(razao_social='C', cnpj=_cnpj(), uf='SP')
        nf = NFeSaida.objects.create(
            numero='RASC-1',
            cliente=cli,
            data=date.today(),
            status='RASCUNHO',
            valor_total=Decimal('200'),
        )
        p_z = _produto('Zebra', 'Z-1')
        p_a = _produto('Alpha', 'A-1')
        ItemNFeSaida.objects.create(nf=nf, produto=p_z, quantidade=Decimal('1'), valor=Decimal('50'))
        ItemNFeSaida.objects.create(nf=nf, produto=p_a, quantidade=Decimal('1'), valor=Decimal('50'))
        descricoes = [it.produto.descricao for it in nf.itens.all()]
        self.assertEqual(descricoes, ['Zebra', 'Alpha'])

    def test_pdf_pedido_preserva_ordem_inclusao(self):
        emp = Empresa.objects.create(razao_social='Emit PDF', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='Cli PDF', cnpj=_cnpj(), uf='SP')
        pedido = PedidoVenda.objects.create(
            numero='PV-PDF',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('300'),
        )
        for desc, cod in (('Item C', 'C-1'), ('Item A', 'A-1'), ('Item B', 'B-1')):
            ItemPedidoVenda.objects.create(
                pedido=pedido,
                produto=_produto(desc, cod),
                quantidade=Decimal('1'),
                valor_unitario=Decimal('100'),
            )
        pdf_bytes = gerar_pedido_venda_pdf_bytes(pedido)
        texto = ''.join(
            page.extract_text() or ''
            for page in PdfReader(io.BytesIO(pdf_bytes)).pages
        )
        self.assertLess(texto.find('C-1'), texto.find('A-1'))
        self.assertLess(texto.find('A-1'), texto.find('B-1'))
