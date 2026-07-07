"""Equivalência / composição física por barra na conferência NF-e entrada."""

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
from apps.fiscal.composicao_fisica_conferencia import (
    ORIGEM_COMPOSICAO_BARRAS,
    REGRA_KG_PARA_M_PESO_POR_METRO,
    quantidade_alvo_composicao_metros,
    validar_composicao_fisica_equivalencias,
)
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


def _setup_tubo_conferencia(
    suffix: str,
    *,
    qty='6.000',
    unidade_nf='M',
    controla_composicao=False,
    unidade_estoque='BR',
    peso_por_metro=None,
) -> dict:
    ppm = Decimal('0.325') if peso_por_metro is None else Decimal(str(peso_por_metro))
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj(), uf='SP')
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FT{suffix}'[:16],
        descricao_base='Tubo',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        usa_conversao_dimensional=True,
        controla_composicao_fisica=controla_composicao,
        unidade_estoque_padrao='M' if controla_composicao else unidade_estoque,
        peso_por_metro_kg=ppm,
        comprimento_padrao_barra_m=Decimal('6'),
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao=f'Tubo {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'T-{suffix}',
        unidade='M' if controla_composicao else unidade_estoque,
        unidade_estoque='M' if controla_composicao else unidade_estoque,
        controla_composicao_fisica=controla_composicao,
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
        prod_json={'CFOP': '5102', 'NCM': '73064000', 'qCom': qty, 'uCom': unidade_nf},
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
    linha.quantidade_nf = Decimal(qty)
    linha.unidade_nf = unidade_nf
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


class ConferenciaComposicaoFisicaTests(TestCase):
    def test_nf_m_tres_barras_soma_ok_grava_estoque_em_m(self):
        ctx = _setup_tubo_conferencia('CF1', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        for ordem, metros in enumerate(['5.800', '6.000', '5.950'], start=1):
            ItemNFeEntradaConferenciaEquivalencia.objects.create(
                item_conferencia=linha,
                ordem=ordem,
                metros=Decimal(metros),
                barras=None,
                peso_kg=None,
            )
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        linha.refresh_from_db()
        self.assertEqual(linha.quantidade_estoque_calculada, Decimal('17.750'))
        self.assertEqual(linha.unidade_estoque_calculada, 'M')
        self.assertEqual(linha.metros_total, Decimal('17.750'))
        self.assertEqual(linha.barras_total, Decimal('3'))
        audit = linha.conversao_estoque_auditoria
        self.assertEqual(audit.get('origem_conversao'), ORIGEM_COMPOSICAO_BARRAS)
        self.assertEqual(len(audit.get('composicao', [])), 3)

    def test_nf_m_soma_divergente_bloqueia(self):
        ctx = _setup_tubo_conferencia('CF2', qty='17.750', controla_composicao=True)
        linha = ctx['linha']
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=1, metros=Decimal('5.800'),
        )
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=2, metros=Decimal('6.000'),
        )
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        erros = validar_equivalencias_quantidade(linha)
        self.assertTrue(erros)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res['aplicado'])

    def test_composicao_nao_usa_br_x_comprimento_padrao(self):
        ctx = _setup_tubo_conferencia('CF3', qty='6.000', controla_composicao=True)
        linha = ctx['linha']
        payload = [{'ordem': 1, 'metros': '', 'barras': '1', 'peso_kg': ''}]
        erros = validar_composicao_fisica_equivalencias(linha, equivalencias_payload=payload)
        self.assertTrue(any('comprimento real em metros' in e for e in erros))

    def test_nf_kg_converte_e_valida_composicao(self):
        # 5.775 kg / 0.325 = 17.769 M (arredondado 3 casas)
        ctx = _setup_tubo_conferencia('CF4', qty='5.775', unidade_nf='KG', controla_composicao=True)
        linha = ctx['linha']
        alvo, erro, meta = quantidade_alvo_composicao_metros(linha)
        self.assertIsNone(erro)
        self.assertEqual(meta['regra_conversao'], REGRA_KG_PARA_M_PESO_POR_METRO)
        self.assertEqual(alvo, Decimal('17.769'))
        payload = [
            {'ordem': 1, 'metros': '5.800', 'barras': '', 'peso_kg': ''},
            {'ordem': 2, 'metros': '6.000', 'barras': '', 'peso_kg': ''},
            {'ordem': 3, 'metros': '5.969', 'barras': '', 'peso_kg': ''},
        ]
        erros = validar_equivalencias_quantidade(linha, equivalencias_payload=payload)
        self.assertEqual(erros, [], erros)

    def test_nf_kg_sem_peso_por_metro_bloqueia(self):
        ctx = _setup_tubo_conferencia('CF5', qty='5.000', unidade_nf='KG', controla_composicao=True, peso_por_metro=0)
        linha = ctx['linha']
        linha.produto.peso_por_metro_kg = None
        linha.produto.familia.peso_por_metro_kg = None
        linha.produto.familia.save(update_fields=['peso_por_metro_kg'])
        linha.produto.save(update_fields=['peso_por_metro_kg'])
        _alvo, erro, _meta = quantidade_alvo_composicao_metros(linha)
        self.assertIn('peso por metro', erro.lower())
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        linha.refresh_from_db()
        self.assertTrue(any('peso por metro' in a.lower() for a in linha.alertas))


class ConferenciaEquivalenciaLegadoTests(TestCase):
    """Produto sem controla_composicao_fisica — comportamento anterior."""

    def test_equivalencia_calcula_totais_em_br(self):
        ctx = _setup_tubo_conferencia('EQ1', controla_composicao=False)
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
        self.assertEqual(linha.unidade_estoque_calculada, 'BR')

    def test_soma_invalida_bloqueia_aplicacao(self):
        ctx = _setup_tubo_conferencia('EQ2', controla_composicao=False)
        linha = ctx['linha']
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=1, metros=Decimal('2'), peso_kg=Decimal('1'),
        )
        ItemNFeEntradaConferenciaEquivalencia.objects.create(
            item_conferencia=linha, ordem=2, metros=Decimal('2'), peso_kg=Decimal('1'),
        )
        erros = validar_equivalencias_quantidade(linha)
        self.assertTrue(erros)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res['aplicado'])

    def test_sem_equivalencia_mantem_conversao_fixa(self):
        ctx = _setup_tubo_conferencia('EQ3', controla_composicao=False)
        linha = ctx['linha']
        aplicar_pos_save_item_conferencia(linha, ctx['conf'])
        linha.refresh_from_db()
        self.assertEqual(linha.quantidade_estoque_calculada, Decimal('1.000'))
        self.assertEqual(linha.barras_total, Decimal('1.000'))

    def test_validacao_converte_br_para_metros_na_nf_m_legado(self):
        ctx = _setup_tubo_conferencia('EQ6', controla_composicao=False)
        linha = ctx['linha']
        payload = [{'ordem': 1, 'metros': '', 'barras': '1', 'peso_kg': ''}]
        erros = validar_equivalencias_quantidade(linha, equivalencias_payload=payload)
        self.assertEqual(erros, [])

    def test_ignorado_nao_cria_equivalencias_no_save(self):
        ctx = _setup_tubo_conferencia('EQ4', controla_composicao=False)
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


class ConferenciaEquivalenciaEntradaAPITests(TestCase):
    def setUp(self):
        self.ctx = _setup_tubo_conferencia('EQA', controla_composicao=True, qty='17.750')
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
                        {'ordem': 1, 'metros': '5.800', 'barras': '', 'peso_kg': ''},
                        {'ordem': 2, 'metros': '6.000', 'barras': '', 'peso_kg': ''},
                    ],
                },
            ],
        }
        r = self.client.post(self.url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_salva_composicao_valida_em_m(self):
        payload = {
            'itens': [
                {
                    'id': self.linha.id,
                    'status': self.linha.status,
                    'equivalencias': [
                        {'ordem': 1, 'metros': '5.800', 'barras': '', 'peso_kg': ''},
                        {'ordem': 2, 'metros': '6.000', 'barras': '', 'peso_kg': ''},
                        {'ordem': 3, 'metros': '5.950', 'barras': '', 'peso_kg': ''},
                    ],
                },
            ],
        }
        r = self.client.post(self.url, payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.linha.refresh_from_db()
        self.assertEqual(self.linha.equivalencias.count(), 3)
        self.assertEqual(self.linha.quantidade_estoque_calculada, Decimal('17.750'))
        self.assertEqual(self.linha.unidade_estoque_calculada, 'M')
