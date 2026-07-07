"""Equivalência manual (metros/barras/kg) por item na conferência NF-e entrada."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.fiscal.aplicacao_estoque_conferencia import aplicar_estoque_fisico_conferencia
from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaConferenciaEquivalencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.fiscal.rastreabilidade_conferencia import validar_equivalencias_quantidade
from apps.fiscal.serializers import ItemNFeEntradaConferenciaSerializer
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _setup_tubo_conferencia(suffix: str, *, qty_m='6.000') -> dict:
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj(), uf='SP')
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FT{suffix}'[:16],
        descricao_base='Tubo',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        usa_conversao_dimensional=True,
        unidade_estoque_padrao='BR',
        peso_por_metro_kg=Decimal('0.325'),
        comprimento_padrao_barra_m=Decimal('6'),
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao=f'Tubo {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'T-{suffix}',
        unidade='BR',
        ncm='73064000',
    )
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=('35' + suffix + 'Z' * 40)[:44],
        numero=f'EQ{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 6, 1, 10, 0)),
        valor_total_nf=Decimal('100'),
        fornecedor_emitente=forn,
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=1,
        prod_json={'CFOP': '5102', 'NCM': '73064000', 'qCom': qty_m, 'uCom': 'M'},
        imposto_json={},
    )
    conf = NFeEntradaConferencia.objects.create(
        nf_entrada_historica=nf,
        status=NFeEntradaConferencia.Status.PREPARADA,
        preparado_em=timezone.now(),
        data_entrada=date(2026, 6, 1),
    )
    linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
    linha.produto = prod
    linha.quantidade_nf = Decimal(qty_m)
    linha.unidade_nf = 'M'
    linha.corrida = 'C-EQ'
    linha.lote = 'L1'
    linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
    linha.save()

    RegraFiscalEntrada.objects.create(
        nome=f'R-EQ-{suffix}',
        ativo=True,
        prioridade=1,
        cfop='5102',
        movimenta_estoque=True,
        severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
    )
    return {'conf': conf, 'linha': linha, 'prod': prod, 'forn': forn, 'nf': nf}


class ConferenciaEquivalenciaEntradaTests(TestCase):
    def test_equivalencia_calcula_totais_em_vez_de_fator_fixo(self):
        ctx = _setup_tubo_conferencia('EQ1')
        linha = ctx['linha']
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=1, metros=Decimal('2'), barras=Decimal('1'), peso_kg=Decimal('1.95'),
        )
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=2, metros=Decimal('2'), barras=Decimal('1'), peso_kg=Decimal('2.10'),
        )
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=3, metros=Decimal('2'), barras=Decimal('1'), peso_kg=Decimal('1.75'),
        )
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        linha.refresh_from_db()
        self.assertEqual(linha.quantidade_estoque_calculada, Decimal('3.000'))
        self.assertEqual(linha.barras_total, Decimal('3.000'))
        self.assertEqual(linha.metros_total, Decimal('6.000'))
        self.assertEqual(linha.peso_total_kg, Decimal('5.800'))
        self.assertEqual(linha.unidade_estoque_calculada, 'BR')

    def test_soma_invalida_bloqueia_aplicacao(self):
        ctx = _setup_tubo_conferencia('EQ2')
        linha = ctx['linha']
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=1, metros=Decimal('2'), peso_kg=Decimal('1'),
        )
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=2, metros=Decimal('2'), peso_kg=Decimal('1'),
        )
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        erros = validar_equivalencias_quantidade(linha)
        self.assertTrue(erros)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res['aplicado'])

    def test_sem_equivalencia_mantem_conversao_fixa(self):
        ctx = _setup_tubo_conferencia('EQ3')
        linha = ctx['linha']
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        linha.refresh_from_db()
        self.assertEqual(linha.quantidade_estoque_calculada, Decimal('1.000'))
        self.assertEqual(linha.barras_total, Decimal('1.000'))

    def test_ignorado_nao_cria_equivalencias_no_save(self):
        ctx = _setup_tubo_conferencia('EQ4')
        linha = ctx['linha']
        ser = ItemNFeEntradaConferenciaSerializer(
            linha,
            data={
                'status': ItemNFeEntradaConferencia.Status.IGNORADO,
                'motivo_ignorado': 'Não entra',
                'equivalencias': [
                    {'ordem': 1, 'metros': '6', 'barras': '1', 'peso_kg': '2'},
                ],
            },
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        linha.refresh_from_db()
        self.assertEqual(linha.equivalencias.count(), 0)

    def test_validacao_converte_br_para_metros_na_nf_m(self):
        ctx = _setup_tubo_conferencia('EQ6')
        linha = ctx['linha']
        payload = [{'ordem': 1, 'metros': '', 'barras': '1', 'peso_kg': ''}]
        erros = validar_equivalencias_quantidade(linha, equivalencias_payload=payload)
        self.assertEqual(erros, [])

    def test_validacao_converte_kg_para_metros_na_nf_m(self):
        ctx = _setup_tubo_conferencia('EQ7')
        linha = ctx['linha']
        # 6 m * 0.325 kg/m = 1.95 kg
        payload = [{'ordem': 1, 'metros': '', 'barras': '', 'peso_kg': '1.95'}]
        erros = validar_equivalencias_quantidade(linha, equivalencias_payload=payload)
        self.assertEqual(erros, [])

    def test_validacao_soma_unidades_mistas_na_nf_m(self):
        ctx = _setup_tubo_conferencia('EQ8')
        linha = ctx['linha']
        payload = [
            {'ordem': 1, 'metros': '2', 'barras': '', 'peso_kg': ''},
            {'ordem': 2, 'metros': '', 'barras': '0.5', 'peso_kg': ''},
            {'ordem': 3, 'metros': '', 'barras': '', 'peso_kg': '0.325'},
        ]
        erros = validar_equivalencias_quantidade(linha, equivalencias_payload=payload)
        self.assertEqual(erros, [])

    def test_remover_equivalencias_volta_conversao_fixa(self):
        ctx = _setup_tubo_conferencia('EQ5')
        linha = ctx['linha']
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=1, metros=Decimal('6'), barras=Decimal('1'), peso_kg=Decimal('2'),
        )
        ser = ItemNFeEntradaConferenciaSerializer(
            linha,
            data={'equivalencias': []},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        linha.refresh_from_db()
        self.assertEqual(linha.equivalencias.count(), 0)
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        linha.refresh_from_db()
        self.assertEqual(linha.quantidade_estoque_calculada, Decimal('1.000'))


class ConferenciaEquivalenciaEntradaAPITests(TestCase):
    def setUp(self):
        self.ctx = _setup_tubo_conferencia('EQA')
        self.linha = self.ctx['linha']
        user = get_user_model().objects.create_user('equiv_api', 'equiv@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user=user)
        self.url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': self.ctx['nf'].pk})

    def test_api_soma_invalida_retorna_400(self):
        payload = {
            'itens': [
                {
                    'id': self.linha.id,
                    'status': self.linha.status,
                    'equivalencias': [
                        {'ordem': 1, 'metros': '2', 'barras': '1', 'peso_kg': '1'},
                        {'ordem': 2, 'metros': '2', 'barras': '1', 'peso_kg': '1'},
                    ],
                },
            ],
        }
        r = self.client.post(self.url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_salva_equivalencia_valida(self):
        payload = {
            'itens': [
                {
                    'id': self.linha.id,
                    'status': self.linha.status,
                    'equivalencias': [
                        {'ordem': 1, 'metros': '2', 'barras': '1', 'peso_kg': '1.95'},
                        {'ordem': 2, 'metros': '2', 'barras': '1', 'peso_kg': '2.10'},
                        {'ordem': 3, 'metros': '2', 'barras': '1', 'peso_kg': '1.75'},
                    ],
                },
            ],
        }
        r = self.client.post(self.url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.linha.refresh_from_db()
        self.assertEqual(self.linha.equivalencias.count(), 3)
        self.assertEqual(self.linha.peso_total_kg, Decimal('5.800'))
        self.assertEqual(self.linha.quantidade_estoque_calculada, Decimal('3.000'))
