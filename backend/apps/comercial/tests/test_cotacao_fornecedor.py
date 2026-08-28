from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import (
    CotacaoFornecedor,
    CotacaoFornecedorItem,
    CotacaoFornecedorParticipante,
    CotacaoFornecedorRespostaItem,
    ItemPedidoCompra,
    ItemPedidoVenda,
    ItemProposta,
    PedidoCompra,
    PedidoVenda,
    Proposta,
)


class CotacaoFornecedorApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cotacao_user', password='x')
        perms = Permission.objects.filter(
            content_type__app_label='comercial',
            codename__in=(
                'view_cotacaofornecedor',
                'add_cotacaofornecedor',
                'change_cotacaofornecedor',
                'registrar_resposta_cotacaofornecedor',
                'selecionar_referencia_cotacaofornecedor',
                'cancel_cotacaofornecedor',
            ),
        )
        self.user.user_permissions.add(*perms)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(razao_social='Cliente Teste', cnpj='12345678000195')
        self.proposta = Proposta.objects.create(
            numero='P-COT-001',
            cliente=self.cliente,
            data=date.today(),
            validade=date.today() + timedelta(days=30),
            status='RASCUNHO',
            valor_frete=Decimal('12.50'),
        )
        self.item_a = ItemProposta.objects.create(
            proposta=self.proposta,
            descricao_avulsa='Item A',
            quantidade=Decimal('10'),
            quantidade_negociada=Decimal('10'),
            valor_unitario=Decimal('100'),
            preco_por_unidade_negociada=Decimal('100'),
        )
        self.item_b = ItemProposta.objects.create(
            proposta=self.proposta,
            descricao_avulsa='Item B',
            quantidade=Decimal('4'),
            quantidade_negociada=Decimal('4'),
            valor_unitario=Decimal('50'),
            preco_por_unidade_negociada=Decimal('50'),
        )
        self.fornecedor_a = Fornecedor.objects.create(razao_social='Fornecedor A', cnpj='11222333000181')
        self.fornecedor_b = Fornecedor.objects.create(razao_social='Fornecedor B', cnpj='44555666000182')

    def _criar_cotacao(self):
        response = self.client.post(
            '/api/cotacoes-fornecedores/',
            {'proposta': self.proposta.pk, 'data': date.today().isoformat(), 'observacao': 'Consulta técnica'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return CotacaoFornecedor.objects.get(pk=response.data['id'])

    def test_cria_cotacao_e_permite_apenas_alguns_itens(self):
        cotacao = self._criar_cotacao()
        response = self.client.post(
            f'/api/cotacoes-fornecedores/{cotacao.pk}/itens/',
            {'item_proposta_id': self.item_a.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(cotacao.itens.count(), 1)
        self.assertEqual(cotacao.itens.get().item_proposta_id, self.item_a.pk)
        self.assertFalse(self.item_b.cotacoes_fornecedores.exists())

    def test_multiplos_fornecedores_e_duplicidade_bloqueada(self):
        cotacao = self._criar_cotacao()
        for fornecedor in (self.fornecedor_a, self.fornecedor_b):
            response = self.client.post(
                f'/api/cotacoes-fornecedores/{cotacao.pk}/participantes/',
                {'fornecedor_id': fornecedor.pk},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        duplicado = self.client.post(
            f'/api/cotacoes-fornecedores/{cotacao.pk}/participantes/',
            {'fornecedor_id': self.fornecedor_a.pk},
            format='json',
        )
        self.assertEqual(duplicado.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cotacao.participantes.count(), 2)

    def test_resposta_parcial_com_recusa_e_sem_retorno(self):
        cotacao = self._criar_cotacao()
        item_a = adicionar_item_api(self.client, cotacao, self.item_a)
        item_b = adicionar_item_api(self.client, cotacao, self.item_b)
        participante = adicionar_participante_api(self.client, cotacao, self.fornecedor_a)
        resposta = self.client.post(
            f'/api/cotacoes-fornecedores/{cotacao.pk}/respostas/',
            {
                'participante_id': participante.pk,
                'cotacao_item_id': item_a.pk,
                'preco_unitario': '12.3456',
                'quantidade_atendida': '5',
                'prazo_entrega': '15 dias',
                'condicao_pagamento': '30 dias',
                'frete': '25.00',
                'frete_tipo': 'FOB',
                'marca_fabricante': 'Marca A',
            },
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertEqual(resposta.data['fornecedor_id'], self.fornecedor_a.pk)
        recusada = self.client.post(
            f'/api/cotacoes-fornecedores/{cotacao.pk}/respostas/',
            {'participante_id': participante.pk, 'cotacao_item_id': item_b.pk, 'status_item': 'RECUSADO'},
            format='json',
        )
        self.assertEqual(recusada.status_code, status.HTTP_200_OK, recusada.data)
        self.assertEqual(CotacaoFornecedorRespostaItem.objects.filter(cotacao_item__cotacao=cotacao).count(), 2)

    def test_comparativo_e_selecao_manual_preserva_historico(self):
        cotacao = self._criar_cotacao()
        item = adicionar_item_api(self.client, cotacao, self.item_a)
        p_a = adicionar_participante_api(self.client, cotacao, self.fornecedor_a)
        p_b = adicionar_participante_api(self.client, cotacao, self.fornecedor_b)
        respostas = []
        for participante, preco in ((p_a, '90.00'), (p_b, '95.00')):
            response = self.client.post(
                f'/api/cotacoes-fornecedores/{cotacao.pk}/respostas/',
                {'participante_id': participante.pk, 'cotacao_item_id': item.pk, 'preco_unitario': preco, 'quantidade_atendida': '10'},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            respostas.append(response.data['id'])
        comparativo = self.client.get(f'/api/cotacoes-fornecedores/{cotacao.pk}/comparativo/')
        self.assertEqual(comparativo.status_code, status.HTTP_200_OK)
        self.assertEqual(len(comparativo.data['itens'][0]['respostas']), 2)
        selecionada = self.client.post(
            f'/api/cotacoes-fornecedores/{cotacao.pk}/selecionar-referencia/',
            {'resposta_id': respostas[1]},
            format='json',
        )
        self.assertEqual(selecionada.status_code, status.HTTP_200_OK, selecionada.data)
        selecionada_novamente = self.client.post(
            f'/api/cotacoes-fornecedores/{cotacao.pk}/selecionar-referencia/',
            {'resposta_id': respostas[0]},
            format='json',
        )
        self.assertEqual(selecionada_novamente.status_code, status.HTTP_200_OK, selecionada_novamente.data)
        self.assertEqual(CotacaoFornecedorRespostaItem.objects.filter(cotacao_item=item).count(), 2)
        self.assertEqual(CotacaoFornecedorRespostaItem.objects.get(pk=respostas[0]).selecionada_como_referencia, True)
        self.assertFalse(CotacaoFornecedorRespostaItem.objects.get(pk=respostas[1]).selecionada_como_referencia)
        self.assertTrue(self.proposta.historico_comercial.filter(tipo_evento='REFERENCIA_COTACAO_SUBSTITUIDA').exists())

    def test_permissao_granular_bloqueia_usuario_sem_acesso(self):
        outro = get_user_model().objects.create_user('cotacao_sem_perm', password='x')
        client = APIClient()
        client.force_authenticate(outro)
        response = client.get('/api/cotacoes-fornecedores/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancelamento_e_nenhum_efeito_em_preco_ou_pedidos(self):
        cotacao = self._criar_cotacao()
        item_proposta_antes = {
            'custo': self.item_a.custo_utilizado,
            'preco': self.item_a.preco_final,
            'sugerido': self.item_a.preco_sugerido,
            'frete': self.proposta.valor_frete,
        }
        response = self.client.post(f'/api/cotacoes-fornecedores/{cotacao.pk}/cancelar/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.item_a.refresh_from_db()
        self.proposta.refresh_from_db()
        self.assertEqual(self.item_a.custo_utilizado, item_proposta_antes['custo'])
        self.assertEqual(self.item_a.preco_final, item_proposta_antes['preco'])
        self.assertEqual(self.item_a.preco_sugerido, item_proposta_antes['sugerido'])
        self.assertEqual(self.proposta.valor_frete, item_proposta_antes['frete'])
        self.assertEqual(PedidoCompra.objects.count(), 0)
        self.assertFalse(PedidoVenda.objects.filter(proposta_id=self.proposta.pk).exists())
        self.assertEqual(ItemPedidoCompra.objects.count(), 0)
        self.assertFalse(ItemPedidoVenda.objects.filter(item_proposta_id=self.item_a.pk).exists())


def adicionar_item_api(client, cotacao, item):
    response = client.post(f'/api/cotacoes-fornecedores/{cotacao.pk}/itens/', {'item_proposta_id': item.pk}, format='json')
    assert response.status_code == status.HTTP_201_CREATED, response.data
    return CotacaoFornecedorItem.objects.get(pk=response.data['id'])


def adicionar_participante_api(client, cotacao, fornecedor):
    response = client.post(f'/api/cotacoes-fornecedores/{cotacao.pk}/participantes/', {'fornecedor_id': fornecedor.pk}, format='json')
    assert response.status_code == status.HTTP_201_CREATED, response.data
    return CotacaoFornecedorParticipante.objects.get(pk=response.data['id'])
