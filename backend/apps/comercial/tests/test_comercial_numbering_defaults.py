"""Comercial 2.2 / 2.2.1 — numeração automática (padrão Pedido de Compra) e defaults."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.converter_proposta_pedido import converter_proposta_em_pedido_venda
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda, ItemProposta, PedidoVenda, Proposta
from apps.comercial.numbering import (
    extrair_sequencial_pedido_venda,
    extrair_sequencial_proposta,
    gerar_numero_pedido_venda,
    gerar_numero_proposta,
)
from apps.comercial.serializers import PedidoVendaSerializer, PropostaSerializer
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'D{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='P',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'C-{suf}',
        unidade='PC',
        ncm='84818200',
    )


class ComercialNumberingDefaultsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('num22', 'num22@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
        self.cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
        self.hoje = date.today()
        self.hoje_iso = self.hoje.isoformat()
        self._re_diario = rf'^PROP-{self.hoje.strftime("%Y%m%d")}-\d{{4}}$'
        self._pv_diario = rf'^PV-{self.hoje.strftime("%Y%m%d")}-\d{{4}}$'

    def test_gerar_numero_proposta_formato(self):
        n1 = gerar_numero_proposta(self.hoje)
        n2 = gerar_numero_proposta(self.hoje)
        self.assertNotEqual(n1, n2)
        self.assertRegex(n1, self._re_diario)
        self.assertIsNotNone(extrair_sequencial_proposta(n1))

    def test_gerar_numero_pedido_formato(self):
        n1 = gerar_numero_pedido_venda(self.hoje)
        n2 = gerar_numero_pedido_venda(self.hoje)
        self.assertNotEqual(n1, n2)
        self.assertRegex(n1, self._pv_diario)

    def test_sequencia_mesmo_dia_incrementa(self):
        n1 = gerar_numero_proposta(self.hoje)
        n2 = gerar_numero_proposta(self.hoje)
        s1 = extrair_sequencial_proposta(n1)
        s2 = extrair_sequencial_proposta(n2)
        self.assertEqual(s2, s1 + 1)

    def test_criar_proposta_sem_numero_via_api(self):
        ser = PropostaSerializer(
            data={
                'cliente_id': self.cli.pk,
                'empresa_emitente_id': self.emp.pk,
                'itens': [
                    {
                        'produto_id': _produto().pk,
                        'quantidade': 1,
                        'valor_unitario': 10,
                        'preco_por_unidade_negociada': 10,
                    },
                ],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        p = ser.save()
        self.assertRegex(p.numero, self._re_diario)
        self.assertEqual(p.status.upper(), 'PENDENTE')
        self.assertIsNotNone(p.data)
        self.assertIsNotNone(p.validade)
        self.assertGreaterEqual((p.validade - p.data).days, 1)

    def test_criar_pedido_sem_numero_status_aberto(self):
        prod = _produto()
        ser = PedidoVendaSerializer(
            data={
                'cliente_id': self.cli.pk,
                'empresa_emitente_id': self.emp.pk,
                'itens': [
                    {
                        'produto_id': prod.pk,
                        'quantidade': 1,
                        'valor_unitario': 50,
                        'preco_por_unidade_negociada': 50,
                    },
                ],
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ped = ser.save()
        self.assertRegex(ped.numero, self._pv_diario)
        self.assertEqual(ped.status, 'ABERTO')
        self.assertIsNotNone(ped.data)

    def test_pedido_legado_pendente_serializa(self):
        ped = PedidoVenda.objects.create(
            numero='LEGADO-XYZ',
            empresa_emitente=self.emp,
            cliente=self.cli,
            data=date.today(),
            status='Pendente',
        )
        data = PedidoVendaSerializer(ped).data
        self.assertEqual(data['status'], 'Pendente')

    def test_conversao_proposta_gera_pedido(self):
        hoje = date.today()
        p = Proposta.objects.create(
            numero=gerar_numero_proposta(hoje),
            data=hoje,
            validade=hoje,
            empresa_emitente=self.emp,
            cliente=self.cli,
            status='Aprovada',
        )
        prod = _produto()
        ItemProposta.objects.create(
            proposta=p,
            produto=prod,
            quantidade=Decimal('1'),
            quantidade_negociada=Decimal('1'),
            valor_unitario=Decimal('10'),
            preco_por_unidade_negociada=Decimal('10'),
        )
        r = converter_proposta_em_pedido_venda(p)
        self.assertFalse(r['ja_existia'])
        ped = PedidoVenda.objects.get(pk=r['pedido_id'])
        self.assertEqual(ped.proposta_id, p.pk)
        self.assertRegex(ped.numero, rf'^PV-{hoje.strftime("%Y%m%d")}-\d{{4}}$')
        self.assertNotIn(p.numero, ped.numero)

    def test_registro_legado_prop_pv_com_hifen_abre(self):
        p = Proposta.objects.create(
            numero='PROP-000099',
            data=date.today(),
            validade=date.today(),
            empresa_emitente=self.emp,
            cliente=self.cli,
            status='PENDENTE',
        )
        ped = PedidoVenda.objects.create(
            numero='PV-000088',
            empresa_emitente=self.emp,
            cliente=self.cli,
            data=date.today(),
            status='Pendente',
        )
        self.assertEqual(PropostaSerializer(p).data['numero'], 'PROP-000099')
        self.assertEqual(PedidoVendaSerializer(ped).data['numero'], 'PV-000088')

    def test_registro_legado_prop_pv_sem_data_diaria_abre(self):
        """Registros criados na fase CQ (PROP{n}/PV{n}) permanecem legíveis."""
        p = Proposta.objects.create(
            numero='PROP42',
            data=date.today(),
            validade=date.today(),
            empresa_emitente=self.emp,
            cliente=self.cli,
            status='PENDENTE',
        )
        ped = PedidoVenda.objects.create(
            numero='PV7',
            empresa_emitente=self.emp,
            cliente=self.cli,
            data=date.today(),
            status='ABERTO',
        )
        self.assertEqual(PropostaSerializer(p).data['numero'], 'PROP42')
        self.assertEqual(PedidoVendaSerializer(ped).data['numero'], 'PV7')

    def test_proposta_vinculada_no_pedido_serializa_numero(self):
        hoje = date.today()
        prop_num = gerar_numero_proposta(hoje)
        p = Proposta.objects.create(
            numero=prop_num,
            data=hoje,
            validade=hoje,
            empresa_emitente=self.emp,
            cliente=self.cli,
            status='Aprovada',
        )
        ItemProposta.objects.create(
            proposta=p,
            produto=_produto(),
            quantidade=Decimal('1'),
            quantidade_negociada=Decimal('1'),
            valor_unitario=Decimal('1'),
            preco_por_unidade_negociada=Decimal('1'),
        )
        r = converter_proposta_em_pedido_venda(p)
        det = PedidoVendaSerializer(PedidoVenda.objects.get(pk=r['pedido_id'])).data
        self.assertEqual(det['proposta_id'], p.pk)
        self.assertEqual(det['proposta_numero'], prop_num)

    def test_faturamento_e_nfe_apos_defaults(self):
        ped = PedidoVenda.objects.create(
            numero=gerar_numero_pedido_venda(date.today()),
            empresa_emitente=self.emp,
            cliente=self.cli,
            data=date.today(),
            status='ABERTO',
        )
        prod = _produto()
        item = ItemPedidoVenda.objects.create(
            pedido=ped,
            produto=prod,
            quantidade=Decimal('2'),
            quantidade_negociada=Decimal('2'),
            valor_unitario=Decimal('10'),
            preco_por_unidade_negociada=Decimal('10'),
            snapshot_fiscal={'ncm': '84818200'},
        )
        criado = criar_faturamento_pedido(ped, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
        confirmar_faturamento_pedido(ped, criado['faturamento_id'])
        fat_id = criado['faturamento_id']
        nfe = gerar_nfe_saida_from_faturamento(ped, fat_id)
        self.assertFalse(nfe['ja_existia'])
