"""Fase 3.8 — AtendimentoEstoque e modo ANTECIPADO na NF de saída."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.cadastros.models import Cliente, Fornecedor
from apps.corridas.models import Corrida
from apps.fiscal.estoque_services import aplicar_todos_itens_saida
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida, ItemNFeSaida, NFeSaida
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _setup_produto_corrida(suffix: str, *, saldo: Decimal = Decimal('100')):
    forn = Fornecedor.objects.create(
        razao_social=f'Forn {suffix}',
        cnpj=f'12.345.678/0001-{suffix[:2]}',
    )
    cliente = Cliente.objects.create(
        razao_social=f'Cliente {suffix}',
        cnpj=f'98.765.432/0001-{suffix[:2]}',
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
    EstoqueCorrida.objects.create(produto=produto, corrida=corrida, saldo=saldo)
    return cliente, produto, corrida


def _payload_nf(
    cliente,
    produto,
    corrida,
    *,
    modo: str = NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
    quantidade: str = '5.000',
    corrida_id: int | None = None,
    item_id: int | None = None,
    numero: str | None = None,
):
    item = {
        'produto_id': produto.id,
        'quantidade': quantidade,
        'valor': '10.00',
    }
    if item_id is not None:
        item['id'] = item_id
    if corrida_id is not None:
        item['corrida_id'] = corrida_id
    return {
        'numero': numero or f'NF-{modo[:3]}-{produto.id}',
        'cliente_id': cliente.id,
        'data': '2026-05-16',
        'status': 'Emitida',
        'modo_atendimento_estoque': modo,
        'itens': [item],
    }


class AtendimentoEstoqueNFeSaidaTests(TestCase):
    def test_imediato_baixa_estoque_corrida(self):
        cliente, produto, corrida = _setup_produto_corrida('im1')
        ser = NFeSaidaSerializer(
            data=_payload_nf(cliente, produto, corrida, corrida_id=corrida.id),
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        ec = EstoqueCorrida.objects.get(produto=produto, corrida=corrida)
        self.assertEqual(ec.saldo, Decimal('95.000'))
        self.assertFalse(
            AtendimentoEstoque.objects.filter(nf_saida=nf)
            .exclude(status=AtendimentoEstoque.Status.CANCELADO)
            .exists(),
        )

    def test_imediato_sem_saldo_bloqueia(self):
        cliente, produto, corrida = _setup_produto_corrida('im2', saldo=Decimal('2'))
        ser = NFeSaidaSerializer(
            data=_payload_nf(cliente, produto, corrida, corrida_id=corrida.id, quantidade='5.000'),
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        with self.assertRaises(ValidationError):
            ser.save()

    def test_antecipado_nao_baixa_estoque(self):
        cliente, produto, corrida = _setup_produto_corrida('an1')
        saldo_antes = EstoqueCorrida.objects.get(produto=produto, corrida=corrida).saldo
        ser = NFeSaidaSerializer(
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                corrida_id=None,
            ),
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        ec = EstoqueCorrida.objects.get(produto=produto, corrida=corrida)
        self.assertEqual(ec.saldo, saldo_antes)

    def test_antecipado_nao_exige_corrida(self):
        cliente, produto, corrida = _setup_produto_corrida('an2')
        ser = NFeSaidaSerializer(
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
            ),
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        item = nf.itens.get()
        self.assertIsNone(item.corrida_id)

    def test_antecipado_cria_atendimento_pendente_por_item(self):
        cliente, produto, corrida = _setup_produto_corrida('an3')
        ser = NFeSaidaSerializer(
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
            ),
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        atend = AtendimentoEstoque.objects.get(nf_saida=nf)
        self.assertEqual(atend.status, AtendimentoEstoque.Status.PENDENTE)
        self.assertEqual(atend.quantidade_atendida, Decimal('0'))
        self.assertFalse(atend.estoque_fisico_aplicado)

    def test_atendimento_guarda_vinculos_e_quantidades(self):
        cliente, produto, corrida = _setup_produto_corrida('an4')
        ser = NFeSaidaSerializer(
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                quantidade='7.500',
            ),
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        nf = ser.save()
        item = nf.itens.get()
        atend = AtendimentoEstoque.objects.get(item_nf_saida=item)
        self.assertEqual(atend.produto_id, produto.id)
        self.assertEqual(atend.nf_saida_id, nf.id)
        self.assertEqual(atend.quantidade_comprometida, Decimal('7.500'))
        self.assertEqual(atend.unidade, 'PC')

    def test_atualizar_quantidade_antecipada_atualiza_comprometida(self):
        cliente, produto, corrida = _setup_produto_corrida('an5')
        create_ser = NFeSaidaSerializer(
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                quantidade='4.000',
            ),
        )
        self.assertTrue(create_ser.is_valid(), create_ser.errors)
        nf = create_ser.save()
        item = nf.itens.get()
        update_ser = NFeSaidaSerializer(
            nf,
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                quantidade='6.000',
                item_id=item.id,
            ),
            partial=False,
        )
        self.assertTrue(update_ser.is_valid(), update_ser.errors)
        update_ser.save()
        atend = AtendimentoEstoque.objects.get(item_nf_saida=item)
        self.assertEqual(atend.quantidade_comprometida, Decimal('6.000'))

    def test_reduzir_quantidade_abaixo_atendida_bloqueia(self):
        from apps.fiscal.tests.test_atendimento_estoque_vinculo_conferencia import _setup_vinculo

        from apps.fiscal.atendimento_estoque import vincular_item_conferencia_a_atendimento

        ctx = _setup_vinculo('RED')
        vincular_item_conferencia_a_atendimento(ctx['linha'], ctx['atend'], '3.000')
        nf = ctx['atend'].nf_saida
        item = nf.itens.get()
        update_ser = NFeSaidaSerializer(
            nf,
            data={
                'numero': nf.numero,
                'cliente_id': ctx['cliente'].id,
                'data': '2026-05-16',
                'status': 'Emitida',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                'itens': [
                    {
                        'id': item.id,
                        'produto_id': ctx['produto'].id,
                        'quantidade': '2.000',
                        'valor': '1.00',
                    },
                ],
            },
        )
        self.assertTrue(update_ser.is_valid(), update_ser.errors)
        with self.assertRaises(ValidationError):
            update_ser.save()

    def test_remover_item_cancela_atendimento(self):
        cliente, produto, corrida = _setup_produto_corrida('an7')
        create_ser = NFeSaidaSerializer(
            data=_payload_nf(
                cliente,
                produto,
                corrida,
                modo=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                numero='NF-AN7-REM',
            ),
        )
        self.assertTrue(create_ser.is_valid(), create_ser.errors)
        nf = create_ser.save()
        item = nf.itens.get()
        atend_id = AtendimentoEstoque.objects.get(item_nf_saida=item).id
        update_ser = NFeSaidaSerializer(
            nf,
            data={
                'numero': nf.numero,
                'cliente_id': cliente.id,
                'data': '2026-05-16',
                'status': 'Emitida',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                'itens': [],
            },
        )
        self.assertTrue(update_ser.is_valid(), update_ser.errors)
        update_ser.save()
        atend = AtendimentoEstoque.objects.get(pk=atend_id)
        self.assertEqual(atend.status, AtendimentoEstoque.Status.CANCELADO)
        self.assertFalse(ItemNFeSaida.objects.filter(pk=item.id).exists())

    def test_nao_permite_dois_atendimentos_ativos_mesmo_item(self):
        cliente, produto, corrida = _setup_produto_corrida('an8')
        nf = NFeSaida.objects.create(
            numero='NF-DUP',
            cliente=cliente,
            data=date(2026, 5, 16),
            modo_atendimento_estoque=NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
        )
        item = ItemNFeSaida.objects.create(
            nf=nf,
            produto=produto,
            quantidade=Decimal('1.000'),
            valor=Decimal('1.00'),
        )
        AtendimentoEstoque.objects.create(
            origem_tipo=AtendimentoEstoque.OrigemTipo.NF_SAIDA,
            item_nf_saida=item,
            nf_saida=nf,
            produto=produto,
            quantidade_comprometida=Decimal('1.000'),
            status=AtendimentoEstoque.Status.PENDENTE,
            unidade='PC',
        )
        with self.assertRaises(IntegrityError):
            AtendimentoEstoque.objects.create(
                origem_tipo=AtendimentoEstoque.OrigemTipo.NF_SAIDA,
                item_nf_saida=item,
                nf_saida=nf,
                produto=produto,
                quantidade_comprometida=Decimal('1.000'),
                status=AtendimentoEstoque.Status.PENDENTE,
                unidade='PC',
            )

    def test_aplicar_saida_direto_ainda_exige_corrida(self):
        """Garante que o serviço de baixa imediata permanece inalterado."""
        cliente, produto, corrida = _setup_produto_corrida('svc')
        nf = NFeSaida.objects.create(numero='NF-SVC', cliente=cliente, data=date(2026, 5, 16))
        item = ItemNFeSaida.objects.create(
            nf=nf,
            produto=produto,
            quantidade=Decimal('1.000'),
            valor=Decimal('1.00'),
        )
        with self.assertRaises(ValueError):
            aplicar_todos_itens_saida(nf)
        item.corrida = corrida
        item.save()
        aplicar_todos_itens_saida(nf)
        ec = EstoqueCorrida.objects.get(produto=produto, corrida=corrida)
        self.assertEqual(ec.saldo, Decimal('99.000'))
