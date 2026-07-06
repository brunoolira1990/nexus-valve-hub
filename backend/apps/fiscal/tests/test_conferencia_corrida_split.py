"""Split de corridas por item na conferência NF-e entrada (v1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.corridas.models import Corrida
from apps.fiscal.aplicacao_estoque_conferencia import (
    aplicar_estoque_fisico_conferencia,
    numero_corrida_sem_rastreabilidade,
)
from apps.fiscal.models import (
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaConferenciaCorridaSplit,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.rastreabilidade_conferencia import validar_splits_quantidade
from apps.fiscal.serializers import ItemNFeEntradaConferenciaSerializer
from apps.fiscal.tests.test_aplicacao_estoque_conferencia import _setup_conferencia
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class ConferenciaCorridaSplitTests(TestCase):
    def test_legado_uma_corrida_aplica_como_antes(self):
        ctx = _setup_conferencia('SP1', corrida='LEG-1', qty='10.000')
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        self.assertEqual(len(res['itens_aplicados']), 1)
        self.assertNotIn('split_ordem', res['itens_aplicados'][0])
        ctx['linha'].refresh_from_db()
        self.assertEqual(ctx['linha'].corrida_estoque.numero, 'LEG-1')
        self.assertEqual(EstoqueCorrida.objects.filter(produto=ctx['prod']).count(), 1)

    def test_split_duas_corridas_cria_dois_estoques(self):
        ctx = _setup_conferencia('SP2', corrida='', qty='2.000')
        linha = ctx['linha']
        linha.corrida = ''
        linha.lote = ''
        linha.save(update_fields=['corrida', 'lote'])
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=1,
            corrida='1242RT',
            lote='',
            quantidade=Decimal('1.000'),
        )
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=2,
            corrida='8215ZL',
            lote='',
            quantidade=Decimal('1.000'),
        )

        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        self.assertEqual(len(res['itens_aplicados']), 2)
        corridas = {row['corrida'] for row in res['itens_aplicados']}
        self.assertEqual(corridas, {'1242RT', '8215ZL'})
        self.assertEqual(EstoqueCorrida.objects.filter(produto=ctx['prod']).count(), 2)
        linha.refresh_from_db()
        self.assertIsNone(linha.corrida_estoque_id)
        splits = list(linha.corridas_split.order_by('ordem'))
        self.assertEqual(len(splits), 2)
        self.assertTrue(all(s.corrida_estoque_id for s in splits))

    def test_soma_invalida_bloqueia_aplicacao(self):
        ctx = _setup_conferencia('SP3', corrida='', qty='2.000')
        linha = ctx['linha']
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=1,
            corrida='A',
            quantidade=Decimal('1.000'),
        )
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=2,
            corrida='B',
            quantidade=Decimal('0.500'),
        )
        erros = validar_splits_quantidade(linha)
        self.assertTrue(erros)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res['aplicado'])
        self.assertTrue(res['pendencias'])

    def test_placeholder_por_sub_linha_sem_corrida(self):
        ctx = _setup_conferencia('SP4', corrida='', qty='2.000')
        linha = ctx['linha']
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=1,
            corrida='',
            quantidade=Decimal('1.000'),
        )
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=2,
            corrida='',
            quantidade=Decimal('1.000'),
        )
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        nums = {row['corrida'] for row in res['itens_aplicados']}
        base = numero_corrida_sem_rastreabilidade(ctx['prod'].id, ctx['forn'].id)
        self.assertEqual(nums, {f'{base}-1', f'{base}-2'})

    def test_ignorado_nao_cria_splits_no_save(self):
        ctx = _setup_conferencia('SP5', corrida='X', qty='1.000')
        linha = ctx['linha']
        ser = ItemNFeEntradaConferenciaSerializer(
            linha,
            data={
                'status': ItemNFeEntradaConferencia.Status.IGNORADO,
                'motivo_ignorado': 'Não entra',
                'corridas_split': [
                    {'ordem': 1, 'corrida': 'A', 'lote': '', 'quantidade': '1.000'},
                ],
            },
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        linha.refresh_from_db()
        self.assertEqual(linha.corridas_split.count(), 0)

    def test_remover_splits_volta_modo_legado(self):
        ctx = _setup_conferencia('SP6', corrida='', qty='3.000')
        linha = ctx['linha']
        ItemNFeEntradaConferenciaCorridaSplit.objects.create(
            item_conferencia=linha,
            ordem=1,
            corrida='OLD',
            quantidade=Decimal('3.000'),
        )
        ser = ItemNFeEntradaConferenciaSerializer(
            linha,
            data={
                'corrida': 'NOVA',
                'lote': 'L9',
                'corridas_split': [],
            },
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        linha.refresh_from_db()
        self.assertEqual(linha.corridas_split.count(), 0)
        self.assertEqual(linha.corrida, 'NOVA')
        self.assertEqual(linha.lote, 'L9')

        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        self.assertEqual(len(res['itens_aplicados']), 1)
        self.assertEqual(res['itens_aplicados'][0]['corrida'], 'NOVA')
        linha.refresh_from_db()
        self.assertIsNotNone(linha.corrida_estoque_id)


class ConferenciaCorridaSplitAPITests(TestCase):
    def setUp(self):
        self.ctx = _setup_conferencia('SPA', corrida='', qty='2.000')
        self.linha = self.ctx['linha']
        user = get_user_model().objects.create_user('split_api', 'split@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user=user)
        self.url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': self.ctx['nf'].pk})

    def test_api_soma_invalida_retorna_400(self):
        payload = {
            'itens': [
                {
                    'id': self.linha.id,
                    'status': self.linha.status,
                    'corridas_split': [
                        {'ordem': 1, 'corrida': 'A', 'lote': '', 'quantidade': '1.000'},
                        {'ordem': 2, 'corrida': 'B', 'lote': '', 'quantidade': '0.500'},
                    ],
                },
            ],
        }
        r = self.client.post(self.url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_salva_split_valido(self):
        payload = {
            'itens': [
                {
                    'id': self.linha.id,
                    'status': self.linha.status,
                    'corridas_split': [
                        {'ordem': 1, 'corrida': '1242RT', 'lote': '', 'quantidade': '1.000'},
                        {'ordem': 2, 'corrida': '8215ZL', 'lote': '', 'quantidade': '1.000'},
                    ],
                },
            ],
        }
        r = self.client.post(self.url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.linha.refresh_from_db()
        self.assertEqual(self.linha.corridas_split.count(), 2)
        self.assertEqual(self.linha.corrida, '')
