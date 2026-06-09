"""ERP 4.0.14.4.1 — Separação pendências operacionais × geração Contas a Pagar NF-e Entrada."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.comercial.models import PedidoCompra
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.nfe_entrada_financeiro import (
    MSG_CONFIRMACAO_PENDENCIAS,
    MSG_SEM_FORNECEDOR,
    MSG_VALOR_ZERO,
    gerar_contas_pagar_de_nfe_entrada,
    montar_flags_financeiro_nfe_entrada,
    preview_contas_pagar_de_nfe_entrada,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _nf_pendente(suffix: str, *, com_item_sem_produto: bool = True) -> tuple[NFeEntradaHistoricaImportada, NFeEntradaConferencia]:
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj())
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'35{suffix}'[:44].ljust(44, '0'),
        numero=f'NF{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 3, 1, 10, 0)),
        valor_total_nf=Decimal('500.00'),
        fornecedor_emitente=forn,
        cstat='100',
    )
    conf = NFeEntradaConferencia.objects.create(
        nf_entrada_historica=nf,
        status=NFeEntradaConferencia.Status.PENDENTE,
    )
    if com_item_sem_produto:
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'xProd': 'Item teste', 'qCom': '10', 'vUnCom': '50', 'vProd': '500'},
        )
        ItemNFeEntradaConferencia.objects.create(
            conferencia=conf,
            item_nfe_historico=item_nf,
            quantidade_nf=Decimal('10'),
            valor_total_nf=Decimal('500'),
            status=ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO,
        )
    return nf, conf


class NFe401441SeparacaoPendenciasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cp401441', 'cp401441@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.nf, self.conf = _nf_pendente('401441')

    def test_preview_com_produto_nao_vinculado(self):
        payload = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.assertTrue(payload['pode_gerar_contas_pagar'])
        self.assertTrue(payload['possui_pendencias_operacionais'])

    def test_flags_com_divergencia_estoque_pendente(self):
        flags = montar_flags_financeiro_nfe_entrada(self.nf)
        self.assertTrue(flags['pode_gerar_contas_pagar'])
        self.assertTrue(flags['possui_pendencias_operacionais'])
        self.assertIn('estoque_nao_aplicado', flags['motivos_pendencias_operacionais'])

    def test_geracao_com_pendencias_exige_confirmacao(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {'parcelas': preview['parcelas']},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(MSG_CONFIRMACAO_PENDENCIAS, res.json()['detail'])

    def test_geracao_com_pendencias_e_confirmacao(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {
                'parcelas': preview['parcelas'],
                'confirmar_pendencias_operacionais': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        titulo = TituloFinanceiro.objects.get(pk=res.json()['titulo']['id'])
        self.assertEqual(titulo.origem_tipo, TituloFinanceiro.OrigemTipo.NFE_ENTRADA)

    def test_geracao_com_pendencias_nao_movimenta_estoque(self):
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        self.client.post(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/gerar-contas-pagar/',
            {
                'parcelas': preview['parcelas'],
                'confirmar_pendencias_operacionais': True,
            },
            format='json',
        )
        self.conf.refresh_from_db()
        self.assertIsNone(self.conf.estoque_aplicado_em)

    def test_geracao_com_pendencias_nao_altera_pedido(self):
        pedido = PedidoCompra.objects.create(
            numero='PC-401441',
            fornecedor=self.nf.fornecedor_emitente,
            data=date(2026, 1, 1),
            valor_total=Decimal('500'),
        )
        status_antes = pedido.status
        self.conf.pedido_compra = pedido
        self.conf.save(update_fields=['pedido_compra'])
        preview = preview_contas_pagar_de_nfe_entrada(self.nf)
        gerar_contas_pagar_de_nfe_entrada(
            self.nf,
            parcelas=preview['parcelas'],
            confirmar_pendencias_operacionais=True,
            usuario=self.user,
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, status_antes)

    def test_fornecedor_ausente_bloqueia_financeiro(self):
        self.nf.fornecedor_emitente = None
        self.nf.save(update_fields=['fornecedor_emitente'])
        flags = montar_flags_financeiro_nfe_entrada(self.nf)
        self.assertFalse(flags['pode_gerar_contas_pagar'])
        self.assertIn(MSG_SEM_FORNECEDOR, flags['motivo_bloqueio_financeiro'])

    def test_valor_zero_bloqueia_financeiro(self):
        self.nf.valor_total_nf = Decimal('0')
        self.nf.save(update_fields=['valor_total_nf'])
        flags = montar_flags_financeiro_nfe_entrada(self.nf)
        self.assertFalse(flags['pode_gerar_contas_pagar'])
        self.assertIn(MSG_VALOR_ZERO, flags['motivo_bloqueio_financeiro'])

    def test_preview_endpoint_com_pendencias(self):
        res = self.client.get(
            f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/financeiro/preview-contas-pagar/',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['possui_pendencias_operacionais'])
        self.assertTrue(data['aviso_pendencias_operacionais'])
