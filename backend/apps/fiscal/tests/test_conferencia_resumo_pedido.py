"""Resumo Pedido × NF na conferência (Fase 2.3)."""

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


class ConferenciaResumoPedidoTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.forn = Fornecedor.objects.create(razao_social=f'Forn RES {s}', cnpj=_cnpj())
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'FR{s}'[:16],
            descricao_base=f'Fam {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao=f'Prod {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'COD-{s}',
            unidade='PC',
        )
        self.pedido = PedidoCompra.objects.create(
            numero=f'PC-RES-{s}',
            fornecedor=self.forn,
            data=date(2026, 1, 15),
        )
        self.item_pc = ItemPedidoCompra.objects.create(
            pedido=self.pedido,
            produto=self.prod,
            quantidade=Decimal('5.000'),
            quantidade_negociada=Decimal('5.000'),
            unidade_negociada='PC',
            valor_unitario=Decimal('10.00'),
            valor_total_item=Decimal('50.00'),
        )
        dh = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=f'35{s}'[:44].ljust(44, '0'),
            numero=f'NF{s}'[:8],
            serie='1',
            modelo='55',
            dh_emissao=dh,
            valor_total_nf=Decimal('50.00'),
            fornecedor_emitente=self.forn,
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'cProd': f'COD-{s}', 'xProd': f'Prod {s}', 'qCom': '5', 'uCom': 'PC', 'vUnCom': '10'},
        )
        self.item_nf_extra = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=2,
            prod_json={'cProd': 'EXTRA', 'xProd': 'Extra NF', 'qCom': '1', 'uCom': 'PC', 'vUnCom': '1'},
        )
        self.conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=self.nf)
        self.linha1, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)
        self.linha2, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf_extra)
        user = get_user_model().objects.create_user(f'res_{s}', f'{s}@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': self.nf.id})

    def test_sem_pedido_retorna_resumo_neutro(self):
        self.conf.pedido_compra = None
        self.conf.save(update_fields=['pedido_compra'])
        resumo = montar_resumo_pedido_conferencia(self.conf)
        self.assertFalse(resumo['pedido_selecionado'])
        self.assertEqual(resumo['totais']['faltantes'], 0)
        self.assertEqual(resumo['totais']['extras'], 0)
        r = self.client.get(self.url, HTTP_HOST='localhost')
        self.assertFalse(r.json()['resumo_pedido']['pedido_selecionado'])

    def test_item_pedido_sem_vinculo_aparece_em_faltantes(self):
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        self.assertEqual(resumo['totais']['faltantes'], 1)
        self.assertEqual(resumo['itens_pedido_sem_nf'][0]['id'], self.item_pc.id)

    def test_linha_nf_sem_pedido_aparece_como_extra(self):
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        self.linha2.item_pedido_compra = None
        self.linha2.status = ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO
        self.linha2.save(update_fields=['item_pedido_compra', 'status'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        extras_ids = [x['id'] for x in resumo['itens_nf_sem_pedido']]
        self.assertIn(self.linha2.id, extras_ids)

    def test_linha_ignorado_nao_conta_como_extra(self):
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        self.linha1.item_pedido_compra = self.item_pc
        self.linha1.save(update_fields=['item_pedido_compra'])
        self.linha2.status = ItemNFeEntradaConferencia.Status.IGNORADO
        self.linha2.item_pedido_compra = None
        self.linha2.motivo_ignorado = 'Servico'
        self.linha2.save(update_fields=['status', 'item_pedido_compra', 'motivo_ignorado'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        self.assertEqual(resumo['totais']['extras'], 0)

    def test_tudo_vinculado_zero_faltantes_extras(self):
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        self.linha1.item_pedido_compra = self.item_pc
        self.linha1.save(update_fields=['item_pedido_compra'])
        self.linha2.status = ItemNFeEntradaConferencia.Status.IGNORADO
        self.linha2.motivo_ignorado = 'Ignorado'
        self.linha2.save(update_fields=['status', 'motivo_ignorado'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        self.assertEqual(resumo['totais']['vinculados'], 1)
        self.assertEqual(resumo['totais']['faltantes'], 0)
        self.assertEqual(resumo['totais']['extras'], 0)

    def test_api_expoe_resumo_pedido(self):
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        r = self.client.get(self.url, HTTP_HOST='localhost')
        self.assertIn('resumo_pedido', r.json())
        self.assertIn('totais', r.json()['resumo_pedido'])
