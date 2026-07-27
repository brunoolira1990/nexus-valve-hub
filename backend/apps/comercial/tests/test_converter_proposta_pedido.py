"""Propostas 2.1 — conversão proposta → pedido de venda."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import ItemPedidoVenda, ItemProposta, PedidoVenda, Proposta
from apps.comercial.commercial_defaults import STATUS_PROPOSTA_CONVERTIDA
from apps.comercial.converter_proposta_pedido import (
    MSG_PROPOSTA_JA_CONVERTIDA,
    STATUS_PEDIDO_INICIAL,
    converter_proposta_em_pedido_venda,
    gerar_pedido_venda_de_proposta,
)
from apps.comercial.proposta_comercial_status import status_item_proposta
from apps.comercial.serializers import recalcular_proposta
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(ncm: str = '84818200') -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'C{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod PV',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PV-{suf}',
        unidade='PC',
        ncm=ncm,
    )


def _proposta_aprovada(*, usar_cenario: bool = False) -> Proposta:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
    hoje = date.today()
    cenario = garantir_cenario_saida_padrao() if usar_cenario else None
    return Proposta.objects.create(
        numero=f'P-{uuid.uuid4().hex[:5]}',
        data=hoje,
        validade=hoje + timedelta(days=30),
        empresa_emitente=emp,
        cliente=cli,
        uf_origem='SP',
        vendedor='Vendedor Teste',
        status='Aprovada',
        condicao_pagamento_texto='À vista',
        dias_parcelas=[0],
        quantidade_parcelas=1,
        usar_cenario_fiscal_saida=usar_cenario,
        cenario_fiscal_saida=cenario,
        homologacao_fiscal_status=Proposta.HomologacaoFiscalStatus.APROVADA if usar_cenario else Proposta.HomologacaoFiscalStatus.NAO_INICIADA,
    )


def _item(proposta: Proposta, prod: Produto, *, icms=Decimal('18')) -> ItemProposta:
    return ItemProposta.objects.create(
        proposta=proposta,
        produto=prod,
        quantidade=Decimal('2'),
        quantidade_negociada=Decimal('2'),
        valor_unitario=Decimal('100'),
        preco_por_unidade_negociada=Decimal('100'),
        desconto=Decimal('5'),
        modo_preco='sugerido',
        icms_saida_percentual=icms,
        pis_saida_percentual=Decimal('1.65'),
        cofins_saida_percentual=Decimal('7.6'),
    )


def _item_avulso(proposta: Proposta, *, icms=Decimal('18')) -> ItemProposta:
    return ItemProposta.objects.create(
        proposta=proposta,
        produto=None,
        descricao_avulsa='Item avulso sem produto',
        ncm_avulso='84818200',
        quantidade=Decimal('1'),
        quantidade_negociada=Decimal('1'),
        valor_unitario=Decimal('50'),
        preco_por_unidade_negociada=Decimal('50'),
        desconto=Decimal('0'),
        modo_preco='sugerido',
        icms_saida_percentual=icms,
        pis_saida_percentual=Decimal('1.65'),
        cofins_saida_percentual=Decimal('7.6'),
    )


class ConverterPropostaPedidoSetupMixin:
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user('conv_pv', 'conv@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cenario = garantir_cenario_saida_padrao()
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818200',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='6102',
            aliquota_icms=Decimal('18'),
        )
        RegraFiscal.objects.create(
            ncm='84818200',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
class ConverterPropostaPedidoTests(ConverterPropostaPedidoSetupMixin, TestCase):
    def test_converter_cria_pedido_e_itens(self):
        p = _proposta_aprovada()
        prod = _produto()
        item = _item(p, prod)
        r = converter_proposta_em_pedido_venda(p)
        self.assertFalse(r['ja_existia'])
        self.assertEqual(r['itens_criados'], 1)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.proposta_id, p.pk)
        self.assertEqual(pedido.status, STATUS_PEDIDO_INICIAL)
        self.assertEqual(pedido.vendedor.upper(), 'VENDEDOR TESTE')
        pv_item = ItemPedidoVenda.objects.get(pedido=pedido)
        self.assertEqual(pv_item.item_proposta_id, item.pk)
        self.assertEqual(pv_item.produto_id, prod.pk)
        self.assertEqual(pv_item.desconto, Decimal('5'))
        self.assertIsNotNone(pv_item.snapshot_fiscal)
        self.assertEqual(pv_item.snapshot_fiscal['origem_regra_fiscal_saida'], 'LEGADO')
        p.refresh_from_db()
        self.assertEqual(p.status, STATUS_PROPOSTA_CONVERTIDA)

    def test_converter_nao_duplica(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r1 = converter_proposta_em_pedido_venda(p)
        with self.assertRaises(ValueError) as ctx:
            converter_proposta_em_pedido_venda(p)
        self.assertEqual(str(ctx.exception), MSG_PROPOSTA_JA_CONVERTIDA)
        self.assertEqual(r1['pedido_id'], PedidoVenda.objects.get(proposta=p).pk)
        self.assertEqual(PedidoVenda.objects.filter(proposta=p).count(), 1)

    def test_converter_cenario_homologado_preserva_origem(self):
        p = _proposta_aprovada(usar_cenario=True)
        _item(p, _produto(), icms=Decimal('18'))
        recalcular_proposta(p)
        r = converter_proposta_em_pedido_venda(p)
        pv_item = ItemPedidoVenda.objects.get(pedido_id=r['pedido_id'])
        self.assertEqual(pv_item.snapshot_fiscal['origem_regra_fiscal_saida'], 'CENARIO_SAIDA')
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertTrue(pedido.snapshot_conversao['usar_cenario_fiscal_saida'])

    def test_proposta_rejeitada_nao_converte(self):
        p = _proposta_aprovada()
        p.status = 'Rejeitada'
        p.save(update_fields=['status'])
        _item(p, _produto())
        with self.assertRaises(ValueError):
            converter_proposta_em_pedido_venda(p)

    def test_api_segunda_conversao_retorna_400(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r1 = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r1.json()['proposta_status'], STATUS_PROPOSTA_CONVERTIDA)
        r2 = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('já foi convertida', r2.json()['detail'].lower())

    def test_proposta_serializa_pedido_vinculado(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        r = self.client.post(f'/api/propostas/{p.pk}/converter-pedido/', {}, format='json')
        pedido_id = r.json()['pedido_id']
        det = self.client.get(f'/api/propostas/{p.pk}/')
        self.assertEqual(det.json()['pedido_venda_id'], pedido_id)
        self.assertFalse(det.json()['pode_converter_em_pedido'])

    def test_listar_pedidos_por_proposta(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        converter_proposta_em_pedido_venda(p)
        r = self.client.get(f'/api/pedidos-venda/?proposta_id={p.pk}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        rows = data if isinstance(data, list) else data.get('results', data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['proposta_id'], p.pk)

    def test_proposta_sem_pedido_abre_normalmente(self):
        p = _proposta_aprovada()
        r = self.client.get(f'/api/propostas/{p.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.json()['pedido_venda_id'])

    def test_valor_total_pedido_arredonda_escala_orm(self):
        """Multiplicação Decimal do ORM pode exceder 2 casas; payload deve quantizar."""
        from apps.comercial.converter_proposta_pedido import _montar_payload_pedido, _valor_item_proposta
        from apps.comercial.serializers import PedidoVendaSerializer

        p = _proposta_aprovada()
        prod = _produto()
        item = _item(p, prod)
        item.refresh_from_db()
        valor_item = _valor_item_proposta(item)
        self.assertEqual(valor_item, Decimal('195.00'))
        self.assertEqual(abs(valor_item.as_tuple().exponent), 2)

        payload = _montar_payload_pedido(p, itens=[item], mensagens=[])
        self.assertEqual(payload['valor_total'], Decimal('195.00'))
        ser = PedidoVendaSerializer(
            data=payload,
            context={'allow_proposta_vinculo': True, 'allow_multi_pedido_proposta': True},
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_gerar_pedido_parcial_item_sem_produto_nao_selecionado(self):
        p = _proposta_aprovada()
        prod = _produto()
        item_vinculado = _item(p, prod)
        item_avulso = _item_avulso(p)
        r = gerar_pedido_venda_de_proposta(
            p,
            itens_payload=[{'proposta_item_id': item_vinculado.pk}],
            acao_itens_nao_selecionados='MANTER_PENDENTE',
        )
        self.assertEqual(r['itens_criados'], 1)
        pedido = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(pedido.itens.count(), 1)
        self.assertEqual(pedido.itens.get().item_proposta_id, item_vinculado.pk)

        item_vinculado.refresh_from_db()
        item_avulso.refresh_from_db()
        self.assertEqual(status_item_proposta(item_vinculado), 'CONVERTIDO_EM_PEDIDO')
        self.assertEqual(status_item_proposta(item_avulso), 'PENDENTE')

        det = self.client.get(f'/api/propostas/{p.pk}/')
        self.assertFalse(det.json()['pode_gerar_pedido'])

    def test_gerar_pedido_parcial_item_selecionado_sem_produto_falha(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        item_avulso = _item_avulso(p)
        with self.assertRaises(ValueError) as ctx:
            gerar_pedido_venda_de_proposta(
                p,
                itens_payload=[{'proposta_item_id': item_avulso.pk}],
            )
        self.assertIn('produto', str(ctx.exception).lower())

    def test_converter_total_exige_todos_itens_com_produto(self):
        p = _proposta_aprovada()
        _item(p, _produto())
        _item_avulso(p)
        with self.assertRaises(ValueError) as ctx:
            converter_proposta_em_pedido_venda(p)
        self.assertIn('produto', str(ctx.exception).lower())


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class ConverterPropostaPedidoCenarioGlobalTests(ConverterPropostaPedidoSetupMixin, TestCase):
    def test_converter_com_flag_global_cenario(self):
        p = _proposta_aprovada(usar_cenario=False)
        _item(p, _produto())
        recalcular_proposta(p)
        r = converter_proposta_em_pedido_venda(p)
        pv_item = ItemPedidoVenda.objects.get(pedido_id=r['pedido_id'])
        self.assertEqual(pv_item.snapshot_fiscal['origem_regra_fiscal_saida'], 'CENARIO_SAIDA')
