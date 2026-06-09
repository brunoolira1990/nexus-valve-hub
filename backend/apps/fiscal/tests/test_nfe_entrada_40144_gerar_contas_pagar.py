"""ERP 4.0.14.4 — Geração manual de Contas a Pagar a partir de NF-e Entrada."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.services.titulo import excluir_titulo_financeiro
from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_entrada_financeiro import (
    MSG_ALERTA_NFE_CANCELADA,
    MSG_CONFIRMACAO_PENDENCIAS,
    MSG_JA_GERADO,
    MSG_SEM_FORNECEDOR,
    montar_flags_financeiro_nfe_entrada,
    preview_contas_pagar_de_nfe_entrada,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _nf_conferida(
    suffix: str,
    *,
    status: str = NFeEntradaConferencia.Status.CONFERIDA,
    duplicatas: bool = False,
    com_pedido: bool = True,
) -> tuple[NFeEntradaHistoricaImportada, NFeEntradaConferencia, PedidoCompra | None]:
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj())
    pedido = None
    if com_pedido:
        fam = FamiliaProduto.objects.create(
            codigo_figura=f'F{suffix}'[:16],
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        prod = Produto.objects.create(
            familia=fam,
            descricao='Produto teste',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo=f'C{suffix}',
            unidade='PC',
            ncm='84818099',
        )
        pedido = PedidoCompra.objects.create(
            numero=f'PC-{suffix}',
            fornecedor=forn,
            data=date(2026, 1, 15),
            valor_total=Decimal('300.00'),
        )
        ItemPedidoCompra.objects.create(
            pedido=pedido,
            produto=prod,
            quantidade=Decimal('10'),
            quantidade_negociada=Decimal('10'),
            valor_unitario=Decimal('30'),
            valor_total_item=Decimal('300'),
        )
    cobr = {}
    if duplicatas:
        cobr = {
            'cobr': {
                'fat': {'nFat': '001', 'vOrig': '300.00', 'vLiq': '300.00'},
                'dup': [
                    {'nDup': '001', 'dVenc': '2026-04-01', 'vDup': '100.00'},
                    {'nDup': '002', 'dVenc': '2026-05-01', 'vDup': '100.00'},
                    {'nDup': '003', 'dVenc': '2026-06-01', 'vDup': '100.00'},
                ],
            },
        }
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'35{suffix}'[:44].ljust(44, '0'),
        numero=f'NF{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 3, 1, 10, 0)),
        valor_total_nf=Decimal('300.00'),
        fornecedor_emitente=forn,
        cstat='100',
        reforma_e_outros_json=cobr,
    )
    conf = NFeEntradaConferencia.objects.create(
        nf_entrada_historica=nf,
        pedido_compra=pedido,
        status=status,
    )
    return nf, conf, pedido


class NFe40144GerarContasPagarTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cp40144', 'cp40144@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.nf, self.conf, self.pedido = _nf_conferida('40144a')

    def test_preview_nfe_entrada_conferida(self):
        payload = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.assertTrue(payload['pode_gerar_contas_pagar'])
        self.assertFalse(payload['financeiro_gerado'])
        self.assertEqual(payload['fornecedor']['id'], self.nf.fornecedor_emitente_id)
        self.assertGreaterEqual(len(payload['parcelas']), 1)
        self.assertEqual(payload['origem']['tipo'], TituloFinanceiro.OrigemTipo.NFE_ENTRADA)

    def test_preview_conferencia_pendente_com_pendencias_operacionais(self):
        self.conf.status = NFeEntradaConferencia.Status.PENDENTE
        self.conf.save(update_fields=['status'])
        payload = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.assertTrue(payload['pode_gerar_contas_pagar'])
        self.assertTrue(payload['possui_pendencias_operacionais'])

    def test_bloqueia_geracao_nfe_cancelada(self):
        self.conf.status = NFeEntradaConferencia.Status.CANCELADA
        self.conf.save(update_fields=['status'])
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': [{'numero_parcela': 1, 'vencimento': date.today().isoformat(), 'valor': '300.00'}]},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('cancelada', res.json()['detail'].lower())

    def test_gerar_titulo_com_parcelas(self):
        preview = self.client.get(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/preview-contas-pagar/',
        )
        self.assertEqual(preview.status_code, 200)
        parcelas = preview.json()['parcelas']
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {
                'parcelas': parcelas,
                'confirmar_pendencias_operacionais': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        self.assertEqual(titulo.tipo, TituloFinanceiro.Tipo.PAGAR)
        self.assertEqual(titulo.origem_tipo, TituloFinanceiro.OrigemTipo.NFE_ENTRADA)
        self.assertEqual(titulo.origem_id, self.nf.pk)
        self.assertEqual(titulo.tipo_lancamento, TituloFinanceiro.TipoLancamentoPagar.FORNECEDOR)

    def test_soma_parcelas_bate_total(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        soma = sum(p.valor_original for p in titulo.parcelas.all())
        self.assertAlmostEqual(float(soma), float(titulo.valor_original), places=2)

    def test_nao_permite_geracao_duplicada(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        res2 = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn(MSG_JA_GERADO, res2.json()['detail'])

    def test_endpoint_contas_pagar_vinculadas(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        res = self.client.get(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/contas-pagar/',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['financeiro_gerado'])
        self.assertEqual(len(res.json()['contas_pagar']), 1)

    def test_titulo_nfe_entrada_nao_pode_ser_excluido(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        with self.assertRaises(ValueError):
            excluir_titulo_financeiro(titulo, motivo='Tentativa', usuario=self.user)

    def test_cancelada_depois_nao_apaga_financeiro(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        titulo_id = res.json()['titulo']['id']
        self.conf.status = NFeEntradaConferencia.Status.CANCELADA
        self.conf.save(update_fields=['status'])
        self.assertTrue(TituloFinanceiro.objects.filter(pk=titulo_id).exists())

    def test_cancelada_depois_alerta_no_titulo(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        titulo_id = res.json()['titulo']['id']
        self.conf.status = NFeEntradaConferencia.Status.CANCELADA
        self.conf.save(update_fields=['status'])
        detail = self.client.get(f'/api/financeiro/contas-pagar/{titulo_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertIn(MSG_ALERTA_NFE_CANCELADA, detail.json()['alerta_origem_cancelada'])

    def test_pedido_compra_nao_alterado(self):
        status_antes = self.pedido.status if self.pedido else ''
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, status_antes)

    def test_importacao_nao_gera_financeiro_automatico(self):
        antes = TituloFinanceiro.objects.filter(
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
            origem_id=self.nf.pk,
        ).count()
        self.assertEqual(antes, 0)
        flags = montar_flags_financeiro_nfe_entrada(self.nf)
        self.assertFalse(flags['financeiro_gerado'])

    def test_duplicatas_xml_tres_parcelas(self):
        nf, conf, _ = _nf_conferida('40144dup', duplicatas=True)
        preview = preview_contas_pagar_de_nfe_entrada(nf)
        self.assertEqual(len(preview['parcelas']), 3)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas'], 'confirmar_pendencias_operacionais': True},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        self.assertEqual(titulo.parcelas.count(), 3)

    def test_soma_invalida_bloqueia(self):
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {
                'parcelas': [
                    {'numero_parcela': 1, 'vencimento': date.today().isoformat(), 'valor': '50.00'},
                ],
                'confirmar_pendencias_operacionais': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('soma', res.json()['detail'].lower())

    def test_conferencia_serializer_financeiro(self):
        from apps.fiscal.serializers import NFeEntradaConferenciaSerializer

        data = NFeEntradaConferenciaSerializer(self.conf).data
        self.assertTrue(data['financeiro']['pode_gerar_contas_pagar'])
