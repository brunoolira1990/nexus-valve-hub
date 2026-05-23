"""Sugestões automáticas de item do pedido na conferência NF-e (Fase 2.2)."""

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
from apps.fiscal.conferencia_pedido import SCORE_SUGESTAO_ALTO_UI, sugerir_itens_pedido_linha
from apps.fiscal.models import (
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class ConferenciaSugestaoItemPedidoTests(TestCase):
    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.suffix = s
        self.forn = Fornecedor.objects.create(razao_social=f'Forn SUG {s}', cnpj=_cnpj())
        self.fam = FamiliaProduto.objects.create(
            codigo_figura=f'FS{s}'[:16],
            descricao_base=f'Fam {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod_a = Produto.objects.create(
            familia=self.fam,
            descricao=f'Produto A {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'COD-A-{s}',
            unidade='PC',
        )
        self.prod_b = Produto.objects.create(
            familia=self.fam,
            descricao=f'Produto B {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'COD-B-{s}',
            unidade='PC',
        )
        self.pedido = PedidoCompra.objects.create(
            numero=f'PC-SUG-{s}',
            fornecedor=self.forn,
            data=date(2026, 1, 15),
        )
        self.item_pc_a = ItemPedidoCompra.objects.create(
            pedido=self.pedido,
            produto=self.prod_a,
            quantidade=Decimal('10.000'),
            quantidade_negociada=Decimal('10.000'),
            unidade_negociada='PC',
            valor_unitario=Decimal('25.50'),
            valor_total_item=Decimal('255.00'),
        )
        self.item_pc_b = ItemPedidoCompra.objects.create(
            pedido=self.pedido,
            produto=self.prod_b,
            quantidade=Decimal('2.000'),
            quantidade_negociada=Decimal('2.000'),
            unidade_negociada='PC',
            valor_unitario=Decimal('10.00'),
            valor_total_item=Decimal('20.00'),
        )
        dh = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=f'35{s}'[:44].ljust(44, '0'),
            numero=f'NF{s}'[:8],
            serie='1',
            modelo='55',
            dh_emissao=dh,
            valor_total_nf=Decimal('255.00'),
            fornecedor_emitente=self.forn,
        )
        self.item_nf_a = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={
                'cProd': f'COD-A-{s}',
                'xProd': f'Produto A {s}',
                'qCom': '10.000',
                'uCom': 'PC',
                'vUnCom': '25.50',
                'vProd': '255.00',
            },
        )
        self.item_nf_b = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=2,
            prod_json={
                'cProd': f'COD-B-{s}',
                'xProd': f'Produto B {s}',
                'qCom': '2.000',
                'uCom': 'PC',
                'vUnCom': '10.00',
                'vProd': '20.00',
            },
        )
        self.conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=self.nf)
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        self.item_conf_a, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf_a)
        self.item_conf_b, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf_b)
        user = get_user_model().objects.create_user(f'sug_{s}', f'{s}@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.url_get = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': self.nf.id})

    def test_mesmo_produto_gera_sugestao_score_alto(self):
        self.item_conf_a.produto = self.prod_a
        self.item_conf_a.save(update_fields=['produto'])
        sugestoes = sugerir_itens_pedido_linha(
            self.item_conf_a,
            [self.item_pc_a, self.item_pc_b],
        )
        self.assertGreaterEqual(len(sugestoes), 1)
        self.assertEqual(sugestoes[0]['id'], self.item_pc_a.id)
        self.assertGreaterEqual(sugestoes[0]['score'], SCORE_SUGESTAO_ALTO_UI)

    def test_codigo_descricao_semelhante_gera_sugestao(self):
        sugestoes = sugerir_itens_pedido_linha(
            self.item_conf_a,
            [self.item_pc_a, self.item_pc_b],
        )
        self.assertGreaterEqual(len(sugestoes), 1)
        self.assertEqual(sugestoes[0]['id'], self.item_pc_a.id)
        self.assertIn('codigo_compativel', sugestoes[0]['motivos'])

    def test_item_ja_vinculado_outra_linha_penalizado(self):
        self.item_conf_a.item_pedido_compra = self.item_pc_a
        self.item_conf_a.save(update_fields=['item_pedido_compra'])
        sugestoes = sugerir_itens_pedido_linha(
            self.item_conf_b,
            [self.item_pc_a, self.item_pc_b],
            vinculados_outras_linhas={self.item_pc_a.id},
        )
        ids = [s['id'] for s in sugestoes]
        self.assertNotIn(self.item_pc_a.id, ids[:1])
        if sugestoes:
            self.assertEqual(sugestoes[0]['id'], self.item_pc_b.id)

    def test_sem_pedido_cabecalho_nao_retorna_sugestoes_api(self):
        self.conf.pedido_compra = None
        self.conf.save(update_fields=['pedido_compra'])
        r = self.client.get(self.url_get, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        for row in r.json()['itens']:
            self.assertEqual(row.get('sugestoes_item_pedido') or [], [])

    def test_get_nao_altera_vinculo_ate_salvar(self):
        self.item_conf_a.produto = self.prod_a
        self.item_conf_a.item_pedido_compra = None
        self.item_conf_a.save(update_fields=['produto', 'item_pedido_compra'])
        r = self.client.get(self.url_get, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        linha = next(x for x in r.json()['itens'] if x['id'] == self.item_conf_a.id)
        self.assertGreaterEqual(len(linha.get('sugestoes_item_pedido') or []), 1)
        self.item_conf_a.refresh_from_db()
        self.assertIsNone(self.item_conf_a.item_pedido_compra_id)

    def test_api_retorna_sugestoes_com_pedido(self):
        self.item_conf_a.produto = self.prod_a
        self.item_conf_a.save(update_fields=['produto'])
        r = self.client.get(self.url_get, HTTP_HOST='localhost')
        linha = next(x for x in r.json()['itens'] if x['id'] == self.item_conf_a.id)
        sugestoes = linha.get('sugestoes_item_pedido') or []
        self.assertGreaterEqual(len(sugestoes), 1)
        self.assertIn('produto_codigo', sugestoes[0])
        self.assertIn('score', sugestoes[0])
        self.assertLessEqual(len(sugestoes), 3)

    def test_vinculo_manual_fase_21_continua_funcionando(self):
        r = self.client.post(
            self.url_get,
            {
                'pedido_compra_id': self.pedido.id,
                'itens': [
                    {
                        'id': self.item_conf_a.id,
                        'item_pedido_compra_id': self.item_pc_a.id,
                        'produto_id': self.prod_a.id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                ],
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(r.status_code, 200)
        self.item_conf_a.refresh_from_db()
        self.assertEqual(self.item_conf_a.item_pedido_compra_id, self.item_pc_a.id)
