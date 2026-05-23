"""NF-e Saída 3 — prévia XML/DANFE."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO, gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import (
    gerar_dados_preview_nfe_saida,
    gerar_preview_danfe_nfe_saida,
    gerar_preview_xml_nfe_saida,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _cliente() -> Cliente:
    return Cliente.objects.create(
        razao_social='Cliente Preview',
        cnpj=_cnpj(),
        ie='123',
        logradouro='Rua X',
        cidade='Rio',
        uf='RJ',
        email='cli@preview.com',
    )


def _empresa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emit Preview',
        cnpj=_cnpj(),
        uf='SP',
        regime_tributario='Lucro Presumido',
        logradouro='Av Y',
        cidade='São Paulo',
    )


def _produto(desc: str) -> Produto:
    suf = uuid.uuid4().hex[:4].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'P{suf}',
        descricao_base='F',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=desc,
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'C-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _nf_rascunho(*, snap_extra: dict | None = None) -> NFeSaida:
    emp = _empresa()
    cli = _cliente()
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=Decimal('200'),
    )
    p1 = _produto('Zebra Item')
    p2 = _produto('Alpha Item')
    snap = {
        'origem_regra_fiscal_saida': 'LEGADO',
        'ncm': '84818200',
        'cfop': '6102',
        'icms_saida_percentual': '12',
        'pis_saida_percentual': '1.65',
        'cofins_saida_percentual': '7.6',
        'recomendacoes_nfe': {
            'ordenar_itens_por_descricao': True,
            'ocultar_destaque_pis_cofins': True,
        },
    }
    if snap_extra:
        snap.update(snap_extra)
    i1 = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=p1,
        quantidade=Decimal('1'),
        quantidade_negociada=Decimal('1'),
        valor_unitario=Decimal('50'),
        preco_por_unidade_negociada=Decimal('50'),
        snapshot_fiscal=dict(snap),
    )
    i2 = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=p2,
        quantidade=Decimal('1'),
        quantidade_negociada=Decimal('1'),
        valor_unitario=Decimal('50'),
        preco_por_unidade_negociada=Decimal('50'),
        snapshot_fiscal=dict(snap),
    )
    criado = criar_faturamento_pedido(
        pedido,
        {
            'itens': [
                {'item_pedido_id': i1.pk, 'quantidade': '1'},
                {'item_pedido_id': i2.pk, 'quantidade': '1'},
            ],
        },
    )
    confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
    fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    return NFeSaida.objects.select_related(
        'cliente', 'pedido_venda__empresa_emitente', 'faturamento_pedido_venda'
    ).prefetch_related('itens__produto').get(pk=r['nfe_saida_id'])


class NFeSaidaPreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('prev_nfe', 'prev@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_preview_xml_rascunho(self):
        nf = _nf_rascunho()
        st_antes = nf.status
        data = gerar_preview_xml_nfe_saida(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.status, st_antes)
        self.assertTrue(data['preview'])
        self.assertIn('<NFe', data['xml'])
        self.assertIn('NÃO TRANSMITIR', data['xml'])
        self.assertIn('<emit>', data['xml'])
        self.assertIn('<dest>', data['xml'])
        self.assertIn('<det ', data['xml'])

    def test_preview_xml_usa_snapshot(self):
        nf = _nf_rascunho()
        item = nf.itens.first()
        self.assertEqual((item.snapshot_fiscal or {}).get('cfop'), '6102')
        data = gerar_preview_xml_nfe_saida(nf)
        self.assertIn('6102', data['xml'])

    def test_preview_xml_nao_altera_financeiro_estoque(self):
        nf = _nf_rascunho()
        atend_antes = AtendimentoEstoque.objects.count()
        tit_antes = list(nf.titulos_receber or [])
        gerar_preview_xml_nfe_saida(nf)
        pdf, _ = gerar_preview_danfe_nfe_saida(nf)
        self.assertGreater(len(pdf), 500)
        nf.refresh_from_db()
        self.assertEqual(nf.titulos_receber, tit_antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)

    def test_preview_com_pendencia_aviso(self):
        nf = _nf_rascunho()
        nf.cliente.cnpj = ''
        nf.cliente.save(update_fields=['cnpj'])
        data = gerar_preview_xml_nfe_saida(nf)
        self.assertTrue(data['preview'])
        self.assertGreater(len(data.get('pendencias') or []), 0)
        self.assertTrue(any('pendências' in m.lower() for m in data.get('mensagens', [])))

    def test_preview_danfe_pdf_valido(self):
        nf = _nf_rascunho()
        pdf, meta = gerar_preview_danfe_nfe_saida(nf)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn('danfe-conferencia', meta['filename'])

    def test_danfe_ordenar_itens_por_descricao(self):
        nf = _nf_rascunho()
        dados = gerar_dados_preview_nfe_saida(nf)
        nomes = [i['x_prod'] for i in dados['itens']]
        self.assertEqual(nomes[0], 'Alpha Item')
        self.assertEqual(nomes[1], 'Zebra Item')

    def test_recomendacoes_aplicadas_e_nao_aplicadas(self):
        nf = _nf_rascunho()
        dados = gerar_dados_preview_nfe_saida(nf)
        aplicadas = dados['recomendacoes']['recomendacoes_aplicadas']
        self.assertTrue(any('ordenados' in a.lower() for a in aplicadas))
        self.assertTrue(any('PIS/COFINS' in a for a in aplicadas))

    def test_manual_alerta(self):
        nf = _nf_rascunho()
        nf.faturamento_pedido_venda_id = None
        nf.save(update_fields=['faturamento_pedido_venda_id'])
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertTrue(dados['origem']['manual'])
        self.assertTrue(any('manual' in a.lower() for a in dados.get('avisos', [])))

    def test_emitida_bloqueada(self):
        nf = _nf_rascunho()
        nf.status = 'Emitida'
        nf.save(update_fields=['status'])
        r = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-xml/')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def test_api_preview_xml_e_danfe(self):
        nf = _nf_rascunho()
        rx = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-xml/')
        self.assertEqual(rx.status_code, status.HTTP_200_OK)
        self.assertIn('xml', rx.json())
        rd = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
        self.assertEqual(rd.status_code, status.HTTP_200_OK)
        self.assertEqual(rd['Content-Type'], 'application/pdf')

    def test_validar_emissao_continua_ok(self):
        nf = _nf_rascunho()
        r = self.client.get(f'/api/nf-saidas/{nf.pk}/validar-emissao/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
