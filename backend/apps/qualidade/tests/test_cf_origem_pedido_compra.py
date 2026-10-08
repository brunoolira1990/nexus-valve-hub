"""Fase 2.8: origem do item CF até Pedido de Compra via item_conferencia."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.conferencia_pedido import build_snapshot_pedido
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada
from apps.qualidade.serializers import ItemCertificadoFornecedorEntradaSerializer


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _grant_cf(user, *, add=False, change=True):
    ct = ContentType.objects.get_for_model(CertificadoFornecedorEntrada)
    if add:
        user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='add_certificadofornecedorentrada'),
        )
    if change:
        user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='change_certificadofornecedorentrada'),
        )
    return get_user_model().objects.get(pk=user.pk)


class CFOrigemPedidoCompraTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.suffix = s
        self.forn = Fornecedor.objects.create(razao_social=f'Forn PC {s}', cnpj=_cnpj())
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'FPC{s}'[:16],
            descricao_base=f'Fam {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao=f'Prod PC {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'COD-PC-{s}',
            unidade='PC',
        )
        self.pedido = PedidoCompra.objects.create(
            numero=f'PC-CF-{s}',
            fornecedor=self.forn,
            data=date(2026, 1, 20),
        )
        self.item_pc = ItemPedidoCompra.objects.create(
            pedido=self.pedido,
            produto=self.prod,
            quantidade=Decimal('10.000'),
            quantidade_negociada=Decimal('10.000'),
            unidade_negociada='PC',
            valor_unitario=Decimal('25.50'),
            valor_total_item=Decimal('255.00'),
        )
        dh = timezone.make_aware(datetime(2026, 3, 1, 10, 0, 0))
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=f'37{s}'[:44].ljust(44, '0'),
            numero=f'NFPC{s}'[:8],
            serie='1',
            modelo='55',
            dh_emissao=dh,
            valor_total_nf=Decimal('255.00'),
            fornecedor_emitente=self.forn,
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'cProd': self.prod.codigo_completo, 'xProd': self.prod.descricao, 'qCom': '10', 'uCom': 'PC'},
        )
        self.conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=self.nf)
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        self.ic, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)
        self.ic.produto = self.prod
        self.ic.status = ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO
        self.ic.save(update_fields=['produto', 'status'])

        u = get_user_model().objects.create_user(f'cf_pc_{s}', f'{s}@test.com', 'x')
        self.user = _grant_cf(u, add=True, change=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url_preencher = reverse('certificado-fornecedor-preencher-por-nfe-entrada')

    def _item_cf_com_conferencia(self, *, com_pedido: bool) -> ItemCertificadoFornecedorEntrada:
        if com_pedido:
            self.ic.item_pedido_compra = self.item_pc
            self.ic.snapshot_pedido = build_snapshot_pedido(self.item_pc)
            self.ic.save(update_fields=['item_pedido_compra', 'snapshot_pedido'])
        else:
            self.ic.item_pedido_compra = None
            self.ic.snapshot_pedido = {}
            self.ic.save(update_fields=['item_pedido_compra', 'snapshot_pedido'])

        cf = CertificadoFornecedorEntrada.objects.create(
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            nf_entrada_historica=self.nf,
            numero_nf_entrada=self.nf.numero,
            serie_nf_entrada=self.nf.serie,
            status='rascunho',
        )
        return ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            ordem=1,
            produto=self.prod,
            codigo_produto=self.prod.codigo_completo,
            descricao_material=self.prod.descricao,
            quantidade=Decimal('10'),
            unidade='PC',
            corrida='CR1',
            norma='ASTM',
            item_conferencia=self.ic,
            origem_nfe_item_numero=1,
        )

    def test_com_item_pedido_retorna_dados_pedido(self):
        item = self._item_cf_com_conferencia(com_pedido=True)
        item = ItemCertificadoFornecedorEntrada.objects.select_related(
            'item_conferencia__item_pedido_compra__pedido',
            'item_conferencia__item_pedido_compra__produto',
            'item_conferencia__conferencia__nf_entrada_historica',
            'item_conferencia__item_nfe_historico',
        ).get(pk=item.pk)
        data = ItemCertificadoFornecedorEntradaSerializer(item).data
        self.assertTrue(data['origem_rastreabilidade_completa'])
        self.assertEqual(data['pedido_compra_id'], self.pedido.id)
        self.assertEqual(data['pedido_compra_numero'], self.pedido.numero)
        self.assertEqual(data['item_pedido_compra_id'], self.item_pc.id)
        self.assertEqual(data['produto_pedido_codigo'], self.prod.codigo_completo)
        self.assertEqual(data['quantidade_pedido'], '10.000')
        self.assertEqual(data['unidade_pedido'], 'PC')
        self.assertIsNotNone(data['item_pedido_resumo'])

    def test_com_conferencia_sem_pedido_retorna_nf_sem_pedido(self):
        item = self._item_cf_com_conferencia(com_pedido=False)
        item = ItemCertificadoFornecedorEntrada.objects.select_related(
            'item_conferencia__item_pedido_compra__pedido',
            'item_conferencia__item_pedido_compra__produto',
        ).get(pk=item.pk)
        data = ItemCertificadoFornecedorEntradaSerializer(item).data
        self.assertFalse(data['origem_rastreabilidade_completa'])
        self.assertIsNone(data['pedido_compra_id'])
        self.assertIsNone(data['item_pedido_compra_id'])
        self.assertTrue(data['origem_produto_vinculado'])

    def test_sem_item_conferencia_continua_valido(self):
        cf = CertificadoFornecedorEntrada.objects.create(
            fornecedor=self.forn,
            fornecedor_nome_snapshot=self.forn.razao_social,
            status='rascunho',
            numero_nf_entrada='MAN',
        )
        item = ItemCertificadoFornecedorEntrada.objects.create(
            certificado_fornecedor=cf,
            ordem=1,
            codigo_produto='X',
            descricao_material='Manual',
            quantidade=Decimal('1'),
            unidade='PC',
            corrida='CR',
            norma='ASTM',
        )
        data = ItemCertificadoFornecedorEntradaSerializer(item).data
        self.assertFalse(data['origem_rastreabilidade_completa'])
        self.assertIsNone(data['origem_nfe_numero'])
        self.assertIsNone(data['pedido_compra_numero'])

    def test_api_preencher_expoe_pedido_quando_vinculado(self):
        self.ic.item_pedido_compra = self.item_pc
        self.ic.snapshot_pedido = build_snapshot_pedido(self.item_pc)
        self.ic.save(update_fields=['item_pedido_compra', 'snapshot_pedido'])
        r = self.client.post(self.url_preencher, {'nf_entrada_historica_id': self.nf.id}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        row = r.json()['itens'][0]
        self.assertTrue(row['origem_rastreabilidade_completa'])
        self.assertEqual(row['pedido_compra_numero'], self.pedido.numero)
