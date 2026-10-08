"""Resumo quantitativo Pedido × NF na mesma conferência (Fase 2.5)."""

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
from apps.fiscal.conferencia_pedido import (
    aplicar_pos_save_item_conferencia,
    calcular_divergencias_item_conferencia,
    montar_resumo_pedido_conferencia,
)
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


class ConferenciaResumoQuantitativoTests(TestCase):
    """Cenários de quantidade por item do pedido na mesma NF."""

    def setUp(self):
        s = uuid.uuid4().hex[:8]
        self.forn = Fornecedor.objects.create(razao_social=f'Forn QTD {s}', cnpj=_cnpj())
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'FQ{s}'[:16],
            descricao_base=f'Fam {s}',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao=f'Prod QTD {s}',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'CODQ-{s}',
            unidade='PC',
            ncm='84818099',
        )
        self.pedido = PedidoCompra.objects.create(
            numero=f'PC-QTD-{s}',
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
        dh = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=f'35{s}'[:44].ljust(44, '0'),
            numero=f'NFQ{s}'[:8],
            serie='1',
            modelo='55',
            dh_emissao=dh,
            valor_total_nf=Decimal('1000.00'),
            fornecedor_emitente=self.forn,
        )
        self.conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=self.nf)
        self.conf.pedido_compra = self.pedido
        self.conf.save(update_fields=['pedido_compra'])
        user = get_user_model().objects.create_user(f'qtd_{s}', f'{s}@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': self.nf.id})

    def _criar_linha_nf(self, n_item: int, qtd: str, *, extra: bool = False) -> ItemNFeEntradaConferencia:
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=n_item,
            prod_json={
                'cProd': 'EXTRA' if extra else self.prod.codigo_completo,
                'xProd': 'Extra' if extra else self.prod.descricao,
                'qCom': qtd,
                'uCom': 'PC',
                'vUnCom': '10',
                'NCM': '84818099',
            },
        )
        linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        linha.quantidade_nf = Decimal(qtd)
        linha.unidade_nf = 'PC'
        linha.valor_unitario_nf = Decimal('10')
        linha.save(update_fields=['quantidade_nf', 'unidade_nf', 'valor_unitario_nf'])
        return linha

    def _row_quantitativo(self, resumo: dict) -> dict:
        rows = resumo['resumo_quantitativo']
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_pedido_100_nf_uma_linha_100_completo(self):
        linha = self._criar_linha_nf(1, '100')
        linha.item_pedido_compra = self.item_pc
        linha.produto = self.prod
        linha.save(update_fields=['item_pedido_compra', 'produto'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        row = self._row_quantitativo(resumo)
        self.assertEqual(row['status_quantitativo'], 'completo')
        self.assertEqual(row['quantidade_nf_vinculada'], 100.0)
        self.assertEqual(row['saldo_na_nf'], 0.0)
        self.assertEqual(resumo['totais']['itens_completos'], 1)
        self.assertNotIn('item_pedido_duplicado_na_nf', row['alertas'])

    def test_pedido_100_nf_duas_linhas_50_50_completo_com_alerta_duplicidade(self):
        linha1 = self._criar_linha_nf(1, '50')
        linha2 = self._criar_linha_nf(2, '50')
        linha1.item_pedido_compra = self.item_pc
        linha2.item_pedido_compra = self.item_pc
        linha1.produto = self.prod
        linha2.produto = self.prod
        linha1.save(update_fields=['item_pedido_compra', 'produto'])
        linha2.save(update_fields=['item_pedido_compra', 'produto'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        row = self._row_quantitativo(resumo)
        self.assertEqual(row['status_quantitativo'], 'completo')
        self.assertEqual(row['quantidade_nf_vinculada'], 100.0)
        self.assertIn('item_pedido_duplicado_na_nf', row['alertas'])
        self.assertEqual(resumo['totais']['itens_duplicados_na_nf'], 1)
        div1, _ = calcular_divergencias_item_conferencia(linha1, self.conf)
        div2, _ = calcular_divergencias_item_conferencia(linha2, self.conf)
        self.assertNotIn('quantidade_diferente', div1)
        self.assertNotIn('quantidade_diferente', div2)

    def test_pedido_100_nf_uma_linha_50_parcial(self):
        linha = self._criar_linha_nf(1, '50')
        linha.item_pedido_compra = self.item_pc
        linha.produto = self.prod
        linha.save(update_fields=['item_pedido_compra', 'produto'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        row = self._row_quantitativo(resumo)
        self.assertEqual(row['status_quantitativo'], 'parcial')
        self.assertEqual(row['saldo_na_nf'], 50.0)
        self.assertIn('quantidade_nf_menor_que_pedido', row['alertas'])
        self.assertEqual(resumo['totais']['itens_parciais'], 1)

    def test_pedido_100_nf_uma_linha_120_excedente(self):
        linha = self._criar_linha_nf(1, '120')
        linha.item_pedido_compra = self.item_pc
        linha.produto = self.prod
        linha.save(update_fields=['item_pedido_compra', 'produto'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        row = self._row_quantitativo(resumo)
        self.assertEqual(row['status_quantitativo'], 'excedente')
        self.assertEqual(row['saldo_na_nf'], -20.0)
        self.assertIn('quantidade_nf_maior_que_pedido', row['alertas'])
        self.assertEqual(resumo['totais']['itens_excedentes'], 1)

    def test_linha_ignorado_nao_entra_na_soma(self):
        linha1 = self._criar_linha_nf(1, '50')
        linha2 = self._criar_linha_nf(2, '50', extra=True)
        linha1.item_pedido_compra = self.item_pc
        linha1.produto = self.prod
        linha1.save(update_fields=['item_pedido_compra', 'produto'])
        linha2.status = ItemNFeEntradaConferencia.Status.IGNORADO
        linha2.motivo_ignorado = 'Servico'
        linha2.item_pedido_compra = self.item_pc
        linha2.save(update_fields=['status', 'motivo_ignorado', 'item_pedido_compra'])
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        row = self._row_quantitativo(resumo)
        self.assertEqual(row['quantidade_nf_vinculada'], 50.0)
        self.assertEqual(row['status_quantitativo'], 'parcial')

    def test_linha_sem_item_pedido_continua_extra(self):
        self._criar_linha_nf(1, '10', extra=True)
        resumo = montar_resumo_pedido_conferencia(self.conf, [self.item_pc])
        self.assertEqual(resumo['totais']['extras'], 1)
        row = self._row_quantitativo(resumo)
        self.assertEqual(row['status_quantitativo'], 'nao_vinculado')

    def test_sem_pedido_resumo_quantitativo_vazio(self):
        self.conf.pedido_compra = None
        self.conf.save(update_fields=['pedido_compra'])
        resumo = montar_resumo_pedido_conferencia(self.conf)
        self.assertEqual(resumo['resumo_quantitativo'], [])
        self.assertEqual(resumo['totais']['itens_parciais'], 0)

    def test_api_expoe_resumo_quantitativo(self):
        linha = self._criar_linha_nf(1, '100')
        linha.item_pedido_compra = self.item_pc
        linha.save(update_fields=['item_pedido_compra'])
        r = self.client.get(self.url, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        rq = r.json()['resumo_pedido']['resumo_quantitativo']
        self.assertEqual(len(rq), 1)
        self.assertEqual(rq[0]['status_quantitativo'], 'completo')

    def test_salvar_split_recalcula_divergencia_irma(self):
        linha1 = self._criar_linha_nf(1, '50')
        linha2 = self._criar_linha_nf(2, '50')
        linha1.item_pedido_compra = self.item_pc
        linha1.produto = self.prod
        linha1.status = ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO
        linha1.save()
        aplicar_pos_save_item_conferencia(linha1, self.conf)
        linha1.refresh_from_db()
        self.assertIn('quantidade_diferente', linha1.divergencias)
        linha2.item_pedido_compra = self.item_pc
        linha2.produto = self.prod
        linha2.status = ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO
        linha2.save()
        aplicar_pos_save_item_conferencia(linha2, self.conf)
        linha1.refresh_from_db()
        linha2.refresh_from_db()
        self.assertNotIn('quantidade_diferente', linha1.divergencias)
        self.assertNotIn('quantidade_diferente', linha2.divergencias)
