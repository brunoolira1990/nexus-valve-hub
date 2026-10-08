"""Saldo acumulado do pedido em múltiplas conferências/NFs (Fase 2.7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.conferencia_pedido import montar_resumo_pedido_conferencia
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class ConferenciaSaldoPedidoGlobalTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.forn = Fornecedor.objects.create(razao_social=f'Forn GLB {s}', cnpj=_cnpj())
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'FG{s}'[:16],
            descricao_base=f'Fam {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao=f'Prod GLB {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'CODG-{s}',
            unidade='PC',
        )
        self.pedido = PedidoCompra.objects.create(
            numero=f'PC-GLB-{s}',
            fornecedor=self.forn,
            data=date(2026, 1, 15),
        )
        self.item_pc = ItemPedidoCompra.objects.create(
            pedido=self.pedido,
            produto=self.prod,
            quantidade=Decimal('100.000'),
            quantidade_negociada=Decimal('100.000'),
            unidade_negociada='PC',
            valor_unitario=Decimal('10.00'),
            valor_total_item=Decimal('1000.00'),
        )
        user = get_user_model().objects.create_user(f'glb_{s}', f'{s}@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def _nf_conferencia(self, suffix: str, numero: str) -> tuple[NFeEntradaHistoricaImportada, NFeEntradaConferencia]:
        dh = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=f'36{suffix}'[:44].ljust(44, '0'),
            numero=numero,
            serie='1',
            modelo='55',
            dh_emissao=dh,
            valor_total_nf=Decimal('1000.00'),
            fornecedor_emitente=self.forn,
        )
        conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=nf)
        conf.pedido_compra = self.pedido
        conf.save(update_fields=['pedido_compra'])
        return nf, conf

    def _linha(
        self,
        conf: NFeEntradaConferencia,
        nf: NFeEntradaHistoricaImportada,
        *,
        n_item: int,
        qtd: str,
        vincular: bool = True,
        ignorado: bool = False,
    ) -> ItemNFeEntradaConferencia:
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=n_item,
            prod_json={'cProd': self.prod.codigo_completo, 'xProd': self.prod.descricao, 'qCom': qtd, 'uCom': 'PC'},
        )
        linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
        linha.quantidade_nf = Decimal(qtd)
        linha.unidade_nf = 'PC'
        if vincular:
            linha.item_pedido_compra = self.item_pc
            linha.produto = self.prod
        if ignorado:
            linha.status = ItemNFeEntradaConferencia.Status.IGNORADO
            linha.motivo_ignorado = 'Ignorado teste'
        linha.save()
        return linha

    def _row_global(self, resumo: dict) -> dict:
        rows = resumo['saldo_pedido_global']
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_pedido_100_nf_atual_100_completo_global(self):
        nf, conf = self._nf_conferencia('a1', 'NF100')
        self._linha(conf, nf, n_item=1, qtd='100')
        row = self._row_global(montar_resumo_pedido_conferencia(conf, [self.item_pc]))
        self.assertEqual(row['status_saldo'], 'completo')
        self.assertEqual(row['quantidade_nf_atual'], 100.0)
        self.assertEqual(row['quantidade_outras_nfs'], 0.0)
        self.assertEqual(row['saldo_pedido'], 0.0)

    def test_pedido_100_nf_atual_50_outra_nf_50_completo_global(self):
        nf1, conf1 = self._nf_conferencia('b1', 'NF50A')
        nf2, conf2 = self._nf_conferencia('b2', 'NF50B')
        self._linha(conf1, nf1, n_item=1, qtd='50')
        self._linha(conf2, nf2, n_item=1, qtd='50')
        row = self._row_global(montar_resumo_pedido_conferencia(conf2, [self.item_pc]))
        self.assertEqual(row['status_saldo'], 'completo')
        self.assertEqual(row['quantidade_nf_atual'], 50.0)
        self.assertEqual(row['quantidade_outras_nfs'], 50.0)
        self.assertEqual(row['quantidade_total_conferida'], 100.0)

    def test_pedido_100_nf_atual_30_outra_50_parcial_saldo_20(self):
        nf1, conf1 = self._nf_conferencia('c1', 'NF30')
        nf2, conf2 = self._nf_conferencia('c2', 'NF50')
        self._linha(conf1, nf1, n_item=1, qtd='50')
        self._linha(conf2, nf2, n_item=1, qtd='30')
        row = self._row_global(montar_resumo_pedido_conferencia(conf2, [self.item_pc]))
        self.assertEqual(row['status_saldo'], 'parcial')
        self.assertEqual(row['quantidade_total_conferida'], 80.0)
        self.assertEqual(row['saldo_pedido'], 20.0)

    def test_pedido_100_nf_atual_120_excedente_global(self):
        nf, conf = self._nf_conferencia('d1', 'NF120')
        self._linha(conf, nf, n_item=1, qtd='120')
        row = self._row_global(montar_resumo_pedido_conferencia(conf, [self.item_pc]))
        self.assertEqual(row['status_saldo'], 'excedente')
        self.assertEqual(row['saldo_pedido'], -20.0)

    def test_linha_ignorado_nao_entra_no_saldo_global(self):
        nf1, conf1 = self._nf_conferencia('e1', 'NF50OK')
        nf2, conf2 = self._nf_conferencia('e2', 'NFIGN')
        self._linha(conf1, nf1, n_item=1, qtd='50')
        self._linha(conf2, nf2, n_item=1, qtd='50', ignorado=True)
        row = self._row_global(montar_resumo_pedido_conferencia(conf2, [self.item_pc]))
        self.assertEqual(row['quantidade_total_conferida'], 50.0)
        self.assertEqual(row['status_saldo'], 'parcial')

    def test_linha_sem_item_pedido_nao_entra_no_saldo_global(self):
        nf, conf = self._nf_conferencia('f1', 'NFEXTRA')
        self._linha(conf, nf, n_item=1, qtd='10', vincular=False)
        row = self._row_global(montar_resumo_pedido_conferencia(conf, [self.item_pc]))
        self.assertEqual(row['quantidade_total_conferida'], 0.0)
        self.assertEqual(row['status_saldo'], 'pendente')

    def test_sem_pedido_saldo_global_vazio(self):
        nf, conf = self._nf_conferencia('g1', 'NFSEM')
        conf.pedido_compra = None
        conf.save(update_fields=['pedido_compra'])
        resumo = montar_resumo_pedido_conferencia(conf)
        self.assertEqual(resumo['saldo_pedido_global'], [])

    def test_api_expoe_saldo_pedido_global(self):
        nf, conf = self._nf_conferencia('h1', 'NFAPI')
        self._linha(conf, nf, n_item=1, qtd='30')
        url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': nf.id})
        r = self.client.get(url, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        self.assertIn('saldo_pedido_global', r.json()['resumo_pedido'])
