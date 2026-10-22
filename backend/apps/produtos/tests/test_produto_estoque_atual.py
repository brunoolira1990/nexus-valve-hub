"""Estoque atual do produto: soma dos saldos das corridas, anotado no queryset (sem N+1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.cadastros.models import Fornecedor
from apps.corridas.models import Corrida
from apps.fiscal.models import EstoqueCorrida
from apps.produtos.estoque_atual import annotate_estoque_atual, estoque_atual_produto
from apps.produtos.models import Produto
from apps.produtos.serializers import ProdutoSerializer

_CONTADOR = [0]


def _produto(codigo: str) -> Produto:
    return Produto.objects.create(
        descricao='FLANGE CEGO ACO CARBONO ANSI 150# RF',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=codigo,
        unidade='PC',
    )


def _corrida(produto: Produto, *, numero: str, saldo: Decimal) -> EstoqueCorrida:
    _CONTADOR[0] += 1
    fornecedor = Fornecedor.objects.create(
        razao_social=f'Fornecedor {numero}',
        cnpj=f'96.543.210/0001-{_CONTADOR[0]:02d}',
    )
    corrida = Corrida.objects.create(
        numero=numero,
        produto=produto,
        fornecedor=fornecedor,
        data_recebimento=date(2026, 9, 1),
    )
    return EstoqueCorrida.objects.create(produto=produto, corrida=corrida, saldo=saldo)


class ProdutoEstoqueAtualSerializerTests(TestCase):
    def test_estoque_atual_e_a_soma_dos_saldos_de_todas_as_corridas(self):
        produto = _produto('EST-001')
        _corrida(produto, numero='CR-EST-1A', saldo=Decimal('10.500'))
        _corrida(produto, numero='CR-EST-1B', saldo=Decimal('3.250'))
        self.assertEqual(ProdutoSerializer(produto).data['estoque_atual'], 13.75)

    def test_produto_sem_corrida_mostra_zero_e_nao_nulo(self):
        produto = _produto('EST-002')
        self.assertEqual(ProdutoSerializer(produto).data['estoque_atual'], 0.0)

    def test_anotacao_do_queryset_bate_com_a_consulta_por_instancia(self):
        produto = _produto('EST-003')
        _corrida(produto, numero='CR-EST-3', saldo=Decimal('26.847'))
        anotado = annotate_estoque_atual(Produto.objects.filter(pk=produto.pk)).first()
        self.assertEqual(anotado.estoque_atual, Decimal('26.847'))
        self.assertEqual(
            ProdutoSerializer(anotado).data['estoque_atual'],
            ProdutoSerializer(produto).data['estoque_atual'],
        )

    def test_consulta_por_instancia_fora_do_queryset_tambem_soma_as_corridas(self):
        produto = _produto('EST-004')
        _corrida(produto, numero='CR-EST-4A', saldo=Decimal('7.000'))
        _corrida(produto, numero='CR-EST-4B', saldo=Decimal('-2.000'))
        self.assertEqual(estoque_atual_produto(produto.pk), Decimal('5.000'))
        self.assertEqual(ProdutoSerializer(Produto.objects.get(pk=produto.pk)).data['estoque_atual'], 5.0)

    def test_estoque_de_um_produto_nao_conta_para_o_outro(self):
        primeiro = _produto('EST-005A')
        segundo = _produto('EST-005B')
        _corrida(primeiro, numero='CR-EST-5A', saldo=Decimal('4.000'))
        _corrida(segundo, numero='CR-EST-5B', saldo=Decimal('9.000'))
        self.assertEqual(ProdutoSerializer(primeiro).data['estoque_atual'], 4.0)

    def test_listagem_com_estoque_anotado_usa_uma_unica_query(self):
        for idx in range(1, 4):
            produto = _produto(f'EST-0{idx + 5}')
            _corrida(produto, numero=f'CR-EST-MULTI-{idx}', saldo=Decimal(idx))
        queryset = annotate_estoque_atual(Produto.objects.filter(codigo_completo__startswith='EST-'))
        with self.assertNumQueries(1):
            linhas = [(p.codigo_completo, p.estoque_atual) for p in queryset]
        self.assertEqual(len(linhas), 3)
        self.assertEqual(sorted(saldo for _, saldo in linhas), [Decimal('1.000'), Decimal('2.000'), Decimal('3.000')])
