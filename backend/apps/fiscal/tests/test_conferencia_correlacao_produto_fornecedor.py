"""Correlação fornecedor × cProd → produto interno na conferência NF-e entrada."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cadastros.models import Fornecedor
from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia
from apps.fiscal.correlacao_produto_fornecedor import (
    buscar_produto_sugerido_correlacao,
    persistir_correlacao_produto_fornecedor_conferencia,
)
from apps.fiscal.models import (
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.serializers import ItemNFeEntradaConferenciaSerializer
from apps.produtos.models import FamiliaProduto, Produto
from apps.produtos.models_equivalencia import FornecedorProdutoEquivalencia, OrigemEquivalencia


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class CorrelacaoProdutoFornecedorConferenciaTests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='Forn Corr', cnpj=_cnpj())
        fam = FamiliaProduto.objects.create(
            codigo_figura='FCOR',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod_a = Produto.objects.create(
            familia=fam,
            descricao='Produto A',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='INT-A',
            unidade='PC',
        )
        self.prod_b = Produto.objects.create(
            familia=fam,
            descricao='Produto B',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='INT-B',
            unidade='PC',
        )
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '9' * 42)[:44],
            numero='NF-CORR',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 4, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
            emit_json={'CNPJ': ''.join(c for c in self.forn.cnpj if c.isdigit())},
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={
                'cProd': 'FORN-123',
                'xProd': 'Item fornecedor 123',
                'NCM': '84818099',
                'qCom': '1',
                'uCom': 'PC',
            },
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=self.nf)
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)

    def test_salva_correlacao_ao_vincular_produto(self):
        self.linha.produto = self.prod_a
        self.linha.save(update_fields=['produto'])
        aplicar_pos_save_item_conferencia(self.linha, self.conf)

        eq = FornecedorProdutoEquivalencia.objects.get(
            fornecedor=self.forn,
            codigo_fornecedor='FORN-123',
        )
        self.assertEqual(eq.produto_interno_id, self.prod_a.id)
        self.assertEqual(eq.origem, OrigemEquivalencia.IMPORTACAO_HISTORICA)
        self.assertTrue(eq.ativo)

    def test_atualiza_correlacao_quando_produto_muda(self):
        self.linha.produto = self.prod_a
        self.linha.save(update_fields=['produto'])
        aplicar_pos_save_item_conferencia(self.linha, self.conf)

        self.linha.produto = self.prod_b
        self.linha.save(update_fields=['produto'])
        aplicar_pos_save_item_conferencia(self.linha, self.conf)

        self.assertEqual(
            FornecedorProdutoEquivalencia.objects.filter(
                fornecedor=self.forn,
                codigo_fornecedor='FORN-123',
            ).count(),
            1,
        )
        eq = FornecedorProdutoEquivalencia.objects.get(fornecedor=self.forn, codigo_fornecedor='FORN-123')
        self.assertEqual(eq.produto_interno_id, self.prod_b.id)

    def test_sugere_produto_por_correlacao_salva(self):
        self.linha.produto = self.prod_a
        self.linha.save(update_fields=['produto'])
        persistir_correlacao_produto_fornecedor_conferencia(self.linha, self.conf)

        nf2 = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '8' * 42)[:44],
            numero='NF-CORR-2',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 4, 2, 10, 0)),
            valor_total_nf=Decimal('50'),
            fornecedor_emitente=self.forn,
            emit_json={'CNPJ': ''.join(c for c in self.forn.cnpj if c.isdigit())},
        )
        item_nf2 = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf2,
            n_item=1,
            prod_json={'cProd': 'FORN-123', 'xProd': 'Item fornecedor 123', 'qCom': '1', 'uCom': 'PC'},
        )
        conf2 = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf2)
        linha2, _ = conf2.itens.get_or_create(item_nfe_historico=item_nf2)

        sug = buscar_produto_sugerido_correlacao(linha2)
        self.assertIsNotNone(sug)
        self.assertEqual(sug['id'], self.prod_a.id)
        self.assertEqual(sug['codigo'], 'INT-A')
        self.assertEqual(sug['codigo_fornecedor'], 'FORN-123')

    def test_sem_sugestao_quando_item_ja_tem_produto(self):
        FornecedorProdutoEquivalencia.objects.create(
            fornecedor=self.forn,
            codigo_fornecedor='FORN-123',
            produto_interno=self.prod_a,
        )
        self.linha.produto = self.prod_b
        self.linha.save(update_fields=['produto'])

        self.assertIsNone(buscar_produto_sugerido_correlacao(self.linha))

    def test_nao_salva_sem_cprod(self):
        self.item_nf.prod_json = {'xProd': 'Sem código', 'qCom': '1', 'uCom': 'PC'}
        self.item_nf.save(update_fields=['prod_json'])
        self.linha.produto = self.prod_a
        self.linha.save(update_fields=['produto'])

        result = persistir_correlacao_produto_fornecedor_conferencia(self.linha, self.conf)
        self.assertIsNone(result)
        self.assertEqual(FornecedorProdutoEquivalencia.objects.count(), 0)

    def test_serializer_expoe_produto_sugerido(self):
        FornecedorProdutoEquivalencia.objects.create(
            fornecedor=self.forn,
            codigo_fornecedor='FORN-123',
            produto_interno=self.prod_a,
            ativo=True,
        )
        data = ItemNFeEntradaConferenciaSerializer().to_representation(self.linha)
        self.assertIsNotNone(data['produto_sugerido'])
        self.assertEqual(data['produto_sugerido']['id'], self.prod_a.id)
        self.assertEqual(data['produto_sugerido']['codigo'], 'INT-A')
