"""Fase 3.9 — listagem de atendimentos e saldos consolidados (read-only)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.corridas.models import Corrida
from apps.fiscal.atendimento_estoque import listar_saldos_consolidados, montar_saldo_consolidado_produto
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida, NFeSaida
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _setup(suffix: str, *, saldo_fisico: Decimal = Decimal('20')):
    forn = Fornecedor.objects.create(
        razao_social=f'Forn {suffix}',
        cnpj=f'11.222.333/0001-{suffix[:2]}',
    )
    cliente = Cliente.objects.create(
        razao_social=f'Cliente {suffix}',
        cnpj=f'99.888.777/0001-{suffix[:2]}',
    )
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    produto = Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    corrida = Corrida.objects.create(
        numero=f'CR-{suffix}',
        produto=produto,
        fornecedor=forn,
        data_recebimento=date(2026, 1, 10),
    )
    EstoqueCorrida.objects.create(produto=produto, corrida=corrida, saldo=saldo_fisico)
    return cliente, produto, corrida


def _criar_nf_antecipada(cliente, produto, numero: str, qtd: str = '10.000'):
    ser = NFeSaidaSerializer(
        data={
            'numero': numero,
            'cliente_id': cliente.id,
            'data': '2026-05-16',
            'status': 'Emitida',
            'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
            'itens': [{'produto_id': produto.id, 'quantidade': qtd, 'valor': '1.00'}],
        },
    )
    assert ser.is_valid(), ser.errors
    return ser.save()


class AtendimentoEstoqueListagemTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user('atend_list', 'atend@test.com', 'secret')
        self.client.force_authenticate(user=user)
        self.cliente, self.produto, _corrida = _setup('LST')
        self.nf = _criar_nf_antecipada(self.cliente, self.produto, 'NF-LST-1')

    def test_listar_atendimentos_pendentes(self):
        url = reverse('atendimento-estoque-list')
        res = self.client.get(url, {'pendentes': 'true'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['status'], AtendimentoEstoque.Status.PENDENTE)

    def test_filtrar_por_status(self):
        atend = AtendimentoEstoque.objects.get(nf_saida=self.nf)
        atend.status = AtendimentoEstoque.Status.CANCELADO
        atend.save()
        url = reverse('atendimento-estoque-list')
        res = self.client.get(url, {'status': AtendimentoEstoque.Status.PENDENTE})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_saldo_consolidado_soma_fisico_estoque_corrida(self):
        saldo = montar_saldo_consolidado_produto(self.produto)
        self.assertEqual(saldo['saldo_fisico'], '20.000')

    def test_saldo_consolidado_soma_comprometido_pendente(self):
        saldo = montar_saldo_consolidado_produto(self.produto)
        self.assertEqual(saldo['quantidade_comprometida'], '10.000')
        self.assertEqual(saldo['quantidade_pendente_atendimento'], '10.000')

    def test_saldo_disponivel_negativo_gera_alerta(self):
        EstoqueCorrida.objects.filter(produto=self.produto).update(saldo=Decimal('0'))
        saldo = montar_saldo_consolidado_produto(self.produto)
        self.assertEqual(saldo['saldo_disponivel'], '-10.000')
        self.assertTrue(
            any('negativo' in a.lower() for a in saldo['alertas']),
        )

    def test_atendimento_cancelado_nao_conta_comprometido(self):
        atend = AtendimentoEstoque.objects.get(nf_saida=self.nf)
        atend.status = AtendimentoEstoque.Status.CANCELADO
        atend.save()
        saldo = montar_saldo_consolidado_produto(self.produto)
        self.assertEqual(saldo['quantidade_comprometida'], '0.000')
        self.assertEqual(saldo['quantidade_pendente_atendimento'], '0.000')

    def test_atendido_sem_fisico_aparece_em_quantidade_atendida_sem_fisico(self):
        atend = AtendimentoEstoque.objects.get(nf_saida=self.nf)
        atend.quantidade_atendida = Decimal('4.000')
        atend.status = AtendimentoEstoque.Status.PARCIAL
        atend.estoque_fisico_aplicado = False
        atend.save()
        saldo = montar_saldo_consolidado_produto(self.produto)
        self.assertEqual(saldo['quantidade_atendida_sem_fisico'], '4.000')

    def test_api_saldos_consolidados_com_produto_id(self):
        url = reverse('estoque-saldos-consolidados-list')
        res = self.client.get(url, {'produto_id': self.produto.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['produto_id'], self.produto.id)
        self.assertEqual(res.data['saldo_fisico'], '20.000')

    def test_listar_saldos_consolidados_todos_produtos(self):
        rows = listar_saldos_consolidados()
        self.assertTrue(any(r['produto_id'] == self.produto.id for r in rows))
