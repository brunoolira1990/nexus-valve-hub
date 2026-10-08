"""ERP 4.0.14.x — busca parcial por número de documento (Pedido de Venda)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import montar_resumo_faturamento
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.core.document_numbering import (
    filtrar_queryset_por_numeros_documento,
    termo_busca_numero_documento_normalizado,
    tokenizar_busca_numero_documento,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod busca',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PB-{suf}',
        unidade='PC',
        ncm='84818200',
    )


class BuscaParcialNumeroDocumentoUnitTests(TestCase):
    def test_normalizacao_remove_separadores(self):
        self.assertEqual(
            termo_busca_numero_documento_normalizado(' pv-20260714-0006 '),
            'PV202607140006',
        )

    def test_filtro_orm_parcial_sem_hifens(self):
        emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='Cli Busca', cnpj=_cnpj(), uf='RJ')
        alvo = PedidoVenda.objects.create(
            numero='PV-20260714-0006',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('100'),
        )
        PedidoVenda.objects.create(
            numero='PV-20190101-0007',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('200'),
        )
        qs = PedidoVenda.objects.all()
        for termo in (
            'PV-20260714-0006',
            'pv-20260714-0006',
            '0006',
            '0714',
            '20260714',
            'PV-2026',
            'PV-20260714',
            'PV202607140006',
        ):
            hit = list(filtrar_queryset_por_numeros_documento(qs, termo, 'numero'))
            self.assertEqual(len(hit), 1, msg=termo)
            self.assertEqual(hit[0].pk, alvo.pk, msg=termo)

        miss = list(filtrar_queryset_por_numeros_documento(qs, '9999', 'numero'))
        self.assertEqual(miss, [])
        miss2 = list(filtrar_queryset_por_numeros_documento(qs, '20260799', 'numero'))
        self.assertEqual(miss2, [])

    def test_multiplos_tokens_preserva_ordem_sem_fuzzy(self):
        """Aceite: sequência contínua vs tokens ordenados; sem fuzzy."""
        emp = Empresa.objects.create(razao_social='Emit Tok', cnpj=_cnpj(), uf='SP')
        cli = Cliente.objects.create(razao_social='Cli Tok', cnpj=_cnpj(), uf='RJ')
        a = PedidoVenda.objects.create(
            numero='PV-20260714-0010',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('10'),
        )
        b = PedidoVenda.objects.create(
            numero='PV-20260715-0010',
            empresa_emitente=emp,
            cliente=cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('20'),
        )
        qs = PedidoVenda.objects.filter(pk__in=[a.pk, b.pk])

        self.assertEqual(tokenizar_busca_numero_documento('0714-0010'), ['0714', '0010'])
        self.assertEqual(tokenizar_busca_numero_documento('0714/0010'), ['0714', '0010'])
        self.assertEqual(tokenizar_busca_numero_documento('PV 0714 0010'), ['PV', '0714', '0010'])
        self.assertEqual(tokenizar_busca_numero_documento('07140010'), ['07140010'])

        # 1–3 / 11: número completo e sequências contínuas sem separadores.
        for termo in (
            'PV-20260714-0010',
            'PV202607140010',
            '202607140010',
            '07140010',
            '7140010',
        ):
            hit = list(filtrar_queryset_por_numeros_documento(qs, termo, 'numero'))
            self.assertEqual([p.numero for p in hit], ['PV-20260714-0010'], msg=termo)

        # 4–6: trecho final simples → ambos.
        so_final = list(filtrar_queryset_por_numeros_documento(qs, '0010', 'numero'))
        self.assertEqual({p.pk for p in so_final}, {a.pk, b.pk})

        # 7–8: tokens com data + sequencial.
        so_a = list(filtrar_queryset_por_numeros_documento(qs, '0714-0010', 'numero'))
        self.assertEqual([p.pk for p in so_a], [a.pk])
        so_b = list(filtrar_queryset_por_numeros_documento(qs, '0715-0010', 'numero'))
        self.assertEqual([p.pk for p in so_b], [b.pk])

        # 9–10: espaço e barra.
        for termo in ('0714 0010', '0714/0010', '714-0010', 'PV 0714 0010', '2026 0714 0010'):
            hit = list(filtrar_queryset_por_numeros_documento(qs, termo, 'numero'))
            self.assertEqual([p.numero for p in hit], ['PV-20260714-0010'], msg=termo)

        # 2026-0010: ambos têm 2026 e 0010 nessa ordem.
        ambos_2026 = list(filtrar_queryset_por_numeros_documento(qs, '2026-0010', 'numero'))
        self.assertEqual({p.pk for p in ambos_2026}, {a.pk, b.pk})

        # 12: ordem invertida.
        self.assertEqual(
            list(filtrar_queryset_por_numeros_documento(qs, '0010-0714', 'numero')),
            [],
        )
        # 13: trecho inexistente / não fuzzy.
        self.assertEqual(
            list(filtrar_queryset_por_numeros_documento(qs, '074-0010', 'numero')),
            [],
        )
        self.assertEqual(
            list(filtrar_queryset_por_numeros_documento(qs, '9999-0010', 'numero')),
            [],
        )
        self.assertEqual(
            list(filtrar_queryset_por_numeros_documento(qs, '0740010', 'numero')),
            [],
        )


class BuscaParcialPedidoVendaApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('buscapv', 'buscapv@test.com', 'x')
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
        self.cli = Cliente.objects.create(razao_social='Cliente PV', cnpj=_cnpj(), uf='RJ')
        self.pedido = PedidoVenda.objects.create(
            numero='PV-20260714-0006',
            empresa_emitente=emp,
            cliente=self.cli,
            data=date.today(),
            status='ABERTO',
            valor_total=Decimal('1500'),
        )
        ItemPedidoVenda.objects.create(
            pedido=self.pedido,
            produto=_produto(),
            quantidade=Decimal('1'),
            quantidade_negociada=Decimal('1'),
            valor_unitario=Decimal('1500'),
            preco_por_unidade_negociada=Decimal('1500'),
        )
        PedidoVenda.objects.create(
            numero='PV-20190101-0099',
            empresa_emitente=emp,
            cliente=self.cli,
            data=date.today(),
            status='CANCEL',
            valor_total=Decimal('10'),
        )

    def _search(self, termo: str, **extra):
        return self.client_api.get('/api/pedidos-venda/', {'search': termo, **extra})

    def test_trechos_e_sem_hifens(self):
        for termo in ('0006', '20260714', 'PV202607140006', 'pv-20260714-0006', 'PV-20260714-0006'):
            r = self._search(termo)
            self.assertEqual(r.status_code, status.HTTP_200_OK, msg=termo)
            nums = [row['numero'] for row in r.data['results']]
            self.assertIn('PV-20260714-0006', nums, msg=termo)
            self.assertEqual(nums.count('PV-20260714-0006'), 1, msg=termo)

    def test_inexistente(self):
        r = self._search('8888')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['results'], [])

    def test_combinacao_status(self):
        r = self._search('0006', status='ABERTO')
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['numero'], 'PV-20260714-0006')
        r2 = self._search('0006', status='CANCEL')
        self.assertEqual(r2.data['results'], [])

    def test_paginacao_com_busca(self):
        r = self._search('0006', page_size=1, page=1)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data['results']), 1)
        self.assertIn('count', r.data)
        self.assertEqual(r.data['count'], 1)

    def test_resultado_expoe_campos_listagem(self):
        r = self._search('0006')
        row = r.data['results'][0]
        self.assertEqual(row['numero'], 'PV-20260714-0006')
        self.assertTrue(row.get('cliente_nome') or row.get('cliente'))
        self.assertEqual(row['status'], 'ABERTO')
        self.assertIn('valor_total', row)

    def test_elegibilidade_faturamento_inalterada(self):
        """Pedido cancelado não fica apto só por aparecer na busca."""
        cancelado = PedidoVenda.objects.get(numero='PV-20190101-0099')
        r = self._search('0099')
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['status'], 'CANCEL')
        resumo = montar_resumo_faturamento(cancelado)
        self.assertFalse(resumo.get('pode_faturar'))

    def test_autocomplete_contrato_preservado(self):
        """limit sem page → lista; shape de opção PC/PV inalterado no service."""
        from apps.comercial.services.alocacao_atendimento_busca import buscar_pedidos_compra_opcoes

        r = self.client_api.get('/api/pedidos-venda/', {'search': '0006', 'limit': 5})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsInstance(r.data, list)
        self.assertTrue(r.data)
        row = r.data[0]
        self.assertIn('id', row)
        self.assertIn('numero', row)
        self.assertEqual(row['numero'], 'PV-20260714-0006')

        opts = buscar_pedidos_compra_opcoes({'search': 'inexistente-xyz', 'limit': 3})
        self.assertIsInstance(opts, list)
        if opts:
            self.assertTrue(
                {'id', 'numero', 'label', 'status'}.issubset(opts[0].keys()),
            )
