"""Concorrência Fase 1 — entrada × venda (sem UniqueConstraint; locks de linhas pai)."""

from __future__ import annotations

import threading
import uuid
from datetime import date, datetime
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.services.alocacao_atendimento_service import AlocacaoAtendimentoErro
from apps.comercial.services.alocacao_entrada_venda_service import (
    alocar_entrada_para_venda,
    atualizar_quantidade_alocacao_entrada_venda,
    total_alocado_destino_pv,
    total_alocado_entrada,
)
from apps.fiscal.models import (
    AlocacaoAtendimento,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(suffix: str) -> Produto:
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FC{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Prod {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PC-{suffix}',
        unidade='PC',
        ncm='84818099',
    )


class AlocacaoEntradaVendaConcorrenciaTests(TransactionTestCase):
    def setUp(self):
        self.produto = _produto(uuid.uuid4().hex[:6])
        self.cliente = Cliente.objects.create(razao_social='Cli Conc', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn Conc', cnpj=_cnpj(), uf='SP')

    def _entrada(self, suffix: str, qty: str = '10.000'):
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + suffix + 'W' * 40)[:44],
            numero=f'N{suffix}'[:8],
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.fornecedor,
            cstat='100',
            tp_amb='1',
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(nf=nf, n_item=1, prod_json={})
        conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=NFeEntradaConferencia.Status.CONFERIDA,
        )
        linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
        linha.produto = self.produto
        linha.quantidade_estoque_calculada = Decimal(qty)
        linha.unidade_estoque_calculada = 'PC'
        linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        linha.save()
        return linha

    def _pv_item(self, numero: str, qty: str = '10'):
        pv = PedidoVenda.objects.create(numero=numero, cliente=self.cliente, data=date(2026, 7, 1))
        return ItemPedidoVenda.objects.create(
            pedido=pv,
            produto=self.produto,
            quantidade=Decimal(qty),
            valor_unitario=Decimal('10'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal(qty),
        )

    def _run_parallel(self, fn_a, fn_b):
        barrier = threading.Barrier(2)
        results: list = [None, None]
        errors: list = [None, None]

        def wrap(idx, fn):
            try:
                barrier.wait(timeout=10)
                results[idx] = fn()
            except Exception as exc:  # noqa: BLE001 — captura para assert
                errors[idx] = exc
            finally:
                connection.close()

        t1 = threading.Thread(target=wrap, args=(0, fn_a))
        t2 = threading.Thread(target=wrap, args=(1, fn_b))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)
        return results, errors

    def test_a_mesma_origem_destino_upsert_sem_duplicidade(self):
        linha = self._entrada('A1')
        pvi = self._pv_item('PV-A1')

        def w1():
            return alocar_entrada_para_venda(
                item_conferencia_id=linha.pk,
                pedido_venda_item_id=pvi.pk,
                quantidade=Decimal('4'),
            )

        def w2():
            return alocar_entrada_para_venda(
                item_conferencia_id=linha.pk,
                pedido_venda_item_id=pvi.pk,
                quantidade=Decimal('7'),
            )

        results, errors = self._run_parallel(w1, w2)
        self.assertTrue(all(e is None or isinstance(e, AlocacaoAtendimentoErro) for e in errors))
        ok = [r for r in results if r is not None]
        self.assertGreaterEqual(len(ok), 1)
        self.assertEqual(AlocacaoAtendimento.objects.filter(
            nf_entrada_historica_item_id=linha.item_nfe_historico_id,
            pedido_venda_item_id=pvi.pk,
        ).count(), 1)
        total = total_alocado_entrada(linha.item_nfe_historico_id)
        self.assertLessEqual(total, Decimal('10') + Decimal('0.0005'))
        self.assertIn(total, (Decimal('4'), Decimal('7')))

    def test_b_mesma_origem_destinos_diferentes_nao_excede(self):
        linha = self._entrada('B1', qty='10.000')
        pvi1 = self._pv_item('PV-B1', qty='10')
        pvi2 = self._pv_item('PV-B2', qty='10')

        def w1():
            return alocar_entrada_para_venda(
                item_conferencia_id=linha.pk,
                pedido_venda_item_id=pvi1.pk,
                quantidade=Decimal('6'),
            )

        def w2():
            return alocar_entrada_para_venda(
                item_conferencia_id=linha.pk,
                pedido_venda_item_id=pvi2.pk,
                quantidade=Decimal('6'),
            )

        results, errors = self._run_parallel(w1, w2)
        sucesso = sum(1 for r in results if r is not None)
        falha = sum(1 for e in errors if isinstance(e, AlocacaoAtendimentoErro))
        self.assertEqual(sucesso + falha, 2)
        self.assertEqual(sucesso, 1)
        self.assertEqual(falha, 1)
        self.assertLessEqual(total_alocado_entrada(linha.item_nfe_historico_id), Decimal('10') + Decimal('0.0005'))

    def test_c_origens_diferentes_mesmo_destino_nao_excede(self):
        linha1 = self._entrada('C1', qty='10.000')
        linha2 = self._entrada('C2', qty='10.000')
        pvi = self._pv_item('PV-C1', qty='10')

        def w1():
            return alocar_entrada_para_venda(
                item_conferencia_id=linha1.pk,
                pedido_venda_item_id=pvi.pk,
                quantidade=Decimal('6'),
            )

        def w2():
            return alocar_entrada_para_venda(
                item_conferencia_id=linha2.pk,
                pedido_venda_item_id=pvi.pk,
                quantidade=Decimal('6'),
            )

        results, errors = self._run_parallel(w1, w2)
        sucesso = sum(1 for r in results if r is not None)
        falha = sum(1 for e in errors if isinstance(e, AlocacaoAtendimentoErro))
        self.assertEqual(sucesso, 1)
        self.assertEqual(falha, 1)
        self.assertLessEqual(total_alocado_destino_pv(pvi.pk), Decimal('10') + Decimal('0.0005'))

    def test_d_edicao_concorrente_nao_excede(self):
        linha = self._entrada('D1', qty='10.000')
        pvi1 = self._pv_item('PV-D1', qty='10')
        pvi2 = self._pv_item('PV-D2', qty='10')
        a1, _ = alocar_entrada_para_venda(
            item_conferencia_id=linha.pk,
            pedido_venda_item_id=pvi1.pk,
            quantidade=Decimal('4'),
        )
        a2, _ = alocar_entrada_para_venda(
            item_conferencia_id=linha.pk,
            pedido_venda_item_id=pvi2.pk,
            quantidade=Decimal('4'),
        )

        def w1():
            return atualizar_quantidade_alocacao_entrada_venda(a1, quantidade=Decimal('6'))

        def w2():
            return atualizar_quantidade_alocacao_entrada_venda(a2, quantidade=Decimal('6'))

        results, errors = self._run_parallel(w1, w2)
        sucesso = sum(1 for r in results if r is not None)
        falha = sum(1 for e in errors if isinstance(e, AlocacaoAtendimentoErro))
        self.assertEqual(sucesso + falha, 2)
        self.assertEqual(sucesso, 1)
        self.assertEqual(falha, 1)
        self.assertLessEqual(total_alocado_entrada(linha.item_nfe_historico_id), Decimal('10') + Decimal('0.0005'))
