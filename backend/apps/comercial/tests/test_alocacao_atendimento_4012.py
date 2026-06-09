"""ERP 4.0.12 — gestão operacional de AlocacaoAtendimento (CRUD + resumo, sem efeitos colaterais)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.faturamento_pedido_venda import montar_resumo_faturamento
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.services.alocacao_atendimento_service import (
    AlocacaoAtendimentoErro,
    atualizar_alocacao_atendimento,
    criar_alocacao_atendimento,
    excluir_alocacao_atendimento,
    validar_quantidades_alocacao,
)
from apps.comercial.services.resumo_atendimento_operacional import (
    obter_resumo_atendimento_operacional,
    obter_resumo_atendimento_pv,
)
from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)
from apps.fiscal.models import AlocacaoAtendimento, AtendimentoEstoque, EstoqueCorrida, NFeSaida
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto


def _produto(suffix: str | None = None) -> Produto:
    suf = suffix or uuid.uuid4().hex[:6]
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suf}'[:16],
        descricao_base=f'Fam {suf}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suf}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suf}',
        unidade='PC',
        ncm='84818099',
    )


class AlocacaoAtendimento4012Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('aloc4012', 'aloc@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('4012')
        self.cliente = Cliente.objects.create(razao_social='Cliente 4012', cnpj='11.111.111/0001-99')
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Forn 4012',
            cnpj='22.222.222/0001-99',
        )
        self.pv = PedidoVenda.objects.create(
            numero='PV-4012',
            cliente=self.cliente,
            data=date(2026, 5, 23),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('100'),
        )

    def _payload_base(self, **extra):
        return {
            'pedido_venda_item_id': self.item_pv.pk,
            'produto_id': self.produto.pk,
            'quantidade_necessaria': '4.000',
            'quantidade_atendida': '0.000',
            'quantidade_pendente': '4.000',
            'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
            'origem_fisica': OrigemFisica.FORNECEDOR,
            'destino_fisico': DestinoFisico.CLIENTE,
            'fornecedor_id': self.fornecedor.pk,
            **extra,
        }

    def test_criar_alocacao_pv_via_api(self):
        r = self.client.post('/api/alocacoes-atendimento/', self._payload_base(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['tipo_atendimento'], TipoAtendimentoItem.RETIRADA_FORNECEDOR)
        self.assertIn('tipo_atendimento_label', r.data)

    def test_criar_sem_pedido_compra(self):
        r = self.client.post('/api/alocacoes-atendimento/', self._payload_base(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(r.data['pedido_compra_item_id'])

    def test_criar_entrega_direta(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            self._payload_base(
                tipo_atendimento=TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE,
                quantidade_necessaria='2.000',
                quantidade_pendente='2.000',
            ),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_criar_entrada_conciliada(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            self._payload_base(
                tipo_atendimento=TipoAtendimentoItem.ENTRADA_CONCILIADA,
                status_entrada_fiscal=StatusEntradaFiscal.CONCILIADA,
                quantidade_atendida='3.000',
                quantidade_pendente='1.000',
                origem_fisica=OrigemFisica.ESTOQUE_PROPRIO,
            ),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_duas_alocacoes_resumo_misto(self):
        self.client.post('/api/alocacoes-atendimento/', self._payload_base(quantidade_necessaria='4.000'), format='json')
        self.client.post(
            '/api/alocacoes-atendimento/',
            self._payload_base(
                quantidade_necessaria='6.000',
                quantidade_pendente='6.000',
                tipo_atendimento=TipoAtendimentoItem.ENTRADA_CONCILIADA,
                status_entrada_fiscal=StatusEntradaFiscal.CONCILIADA,
            ),
            format='json',
        )
        res = obter_resumo_atendimento_pv(self.pv)
        self.assertTrue(res['atendimento_misto'])

    def test_bloqueia_quantidade_negativa(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            self._payload_base(quantidade_atendida='-1'),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bloqueia_soma_maior_que_item_pv(self):
        self.client.post(
            '/api/alocacoes-atendimento/',
            self._payload_base(quantidade_necessaria='7.000', quantidade_pendente='7.000'),
            format='json',
        )
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            self._payload_base(quantidade_necessaria='5.000', quantidade_pendente='5.000'),
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atualizar_e_excluir(self):
        cri = self.client.post('/api/alocacoes-atendimento/', self._payload_base(), format='json')
        pk = cri.data['id']
        patch = self.client.patch(
            f'/api/alocacoes-atendimento/{pk}/',
            {'observacao_operacional': 'Atualizado'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['observacao_operacional'], 'Atualizado')
        del_r = self.client.delete(f'/api/alocacoes-atendimento/{pk}/')
        self.assertEqual(del_r.status_code, status.HTTP_204_NO_CONTENT)

    def test_resumo_pv_reflete_alocacao(self):
        self.client.post('/api/alocacoes-atendimento/', self._payload_base(), format='json')
        r = self.client.get(f'/api/pedidos-venda/{self.pv.pk}/alocacoes-atendimento/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertTrue(r.data['resumo_atendimento_operacional']['tem_alocacao'])

    def test_resumo_faturamento_reflete_alocacao(self):
        criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_pendente': Decimal('2'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
            },
        )
        resumo = montar_resumo_faturamento(self.pv)
        self.assertTrue(resumo['resumo_atendimento_operacional']['tem_alocacao'])

    def test_resumo_nfe_saida_reflete_alocacao(self):
        nf = NFeSaida.objects.create(
            numero='NF-4012',
            cliente=self.cliente,
            pedido_venda=self.pv,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('100'),
        )
        criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
            },
        )
        r = self.client.get(f'/api/nf-saidas/{nf.pk}/alocacoes-atendimento/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['resumo_atendimento_operacional']['tem_alocacao'])

    def test_nao_movimenta_estoque(self):
        estoque_antes = EstoqueCorrida.objects.count()
        atend_antes = AtendimentoEstoque.objects.count()
        criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
        )
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)

    def test_nao_altera_nfe(self):
        nf = NFeSaida.objects.create(
            numero='NF-4012B',
            cliente=self.cliente,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('50'),
        )
        status_antes = nf.status
        self.client.post('/api/alocacoes-atendimento/', self._payload_base(), format='json')
        nf.refresh_from_db()
        self.assertEqual(nf.status, status_antes)
        data = NFeSaidaSerializer(nf).data
        self.assertEqual(data['status'], status_antes)

    def test_entrada_pendente_nao_bloqueia_nfe(self):
        criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('10'),
                'quantidade_pendente': Decimal('10'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
            },
        )
        nf = NFeSaida.objects.create(
            numero='NF-4012C',
            cliente=self.cliente,
            pedido_venda=self.pv,
            data=date(2026, 5, 23),
            status='Rascunho',
            valor_total=Decimal('100'),
        )
        res = obter_resumo_atendimento_operacional(nf, contexto='nfe_saida')
        self.assertTrue(res['possui_entrada_pendente'])
        self.assertNotIn('bloqueia', (res.get('mensagem') or '').lower())

    def test_listagem_api_autenticada(self):
        self.client.post('/api/alocacoes-atendimento/', self._payload_base(), format='json')
        r = self.client.get(f'/api/alocacoes-atendimento/?pedido_venda={self.pv.pk}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data.get('results', r.data)
        self.assertGreaterEqual(len(results), 1)

    def test_service_atualizar_validacao(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_pendente': Decimal('2'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
        )
        atualizar_alocacao_atendimento(aloc, {'observacao_operacional': 'ok'})
        aloc.refresh_from_db()
        self.assertEqual(aloc.observacao_operacional, 'ok')

    def test_service_excluir(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.NAO_DEFINIDO,
            },
        )
        excluir_alocacao_atendimento(aloc)
        self.assertFalse(AlocacaoAtendimento.objects.filter(pk=aloc.pk).exists())

    def test_quantidade_atendida_mais_pendente_maior_que_necessaria(self):
        with self.assertRaises(AlocacaoAtendimentoErro):
            validar_quantidades_alocacao(
                pedido_venda_item_id=self.item_pv.pk,
                quantidade_necessaria=Decimal('5'),
                quantidade_atendida=Decimal('4'),
                quantidade_pendente=Decimal('4'),
            )
