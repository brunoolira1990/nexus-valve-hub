"""Fase 3.11 — aplicação física de estoque a partir da conferência NF-e entrada."""

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
from apps.corridas.models import Corrida
from apps.fiscal.aplicacao_estoque_conferencia import (
    aplicar_estoque_fisico_conferencia,
    numero_corrida_sem_rastreabilidade,
)
from apps.fiscal.atendimento_estoque import montar_saldo_consolidado_produto, vincular_item_conferencia_a_atendimento
from apps.fiscal.models import (
    AtendimentoEstoque,
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaida,
)
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _setup_conferencia(suffix: str, *, movimenta=True, corrida='C-APL', qty='10.000'):
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj(), uf='SP')
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FA{suffix}'[:16],
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao=f'Prod {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'P-{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=('35' + suffix + 'Y' * 40)[:44],
        numero=f'NE{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 6, 1, 10, 0)),
        valor_total_nf=Decimal('100'),
        fornecedor_emitente=forn,
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=1,
        prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': qty, 'uCom': 'PC'},
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
    linha.unidade_nf = 'PC'
    linha.quantidade_estoque_calculada = Decimal(qty)
    linha.corrida = corrida
    linha.lote = 'L1'
    linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
    linha.save()

    RegraFiscalEntrada.objects.create(
        nome=f'R-{suffix}',
        ativo=True,
        prioridade=1,
        cfop='5102',
        movimenta_estoque=movimenta,
        severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
    )
    return {'conf': conf, 'linha': linha, 'prod': prod, 'forn': forn, 'nf': nf}


class AplicacaoEstoqueConferenciaTests(TestCase):
    def test_saldo_consolidado_reflete_aplicacao_fisica(self):
        ctx = _setup_conferencia('A0')
        antes = montar_saldo_consolidado_produto(ctx['prod'])
        self.assertEqual(Decimal(antes['saldo_fisico']), Decimal('0'))
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        depois = montar_saldo_consolidado_produto(ctx['prod'])
        self.assertEqual(Decimal(depois['saldo_fisico']), Decimal('10.000'))

    def test_aplicar_incrementa_estoque_corrida(self):
        ctx = _setup_conferencia('A1')
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        self.assertEqual(len(res['itens_aplicados']), 1)
        ec = EstoqueCorrida.objects.get(produto=ctx['prod'])
        self.assertEqual(ec.saldo, Decimal('10.000'))
        ctx['linha'].refresh_from_db()
        self.assertIsNotNone(ctx['linha'].estoque_aplicado_em)
        self.assertEqual(ctx['linha'].quantidade_estoque_aplicada, Decimal('10.000'))

    def test_aplicar_cria_corrida_mestre(self):
        ctx = _setup_conferencia('A2', corrida='363')
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        corrida = Corrida.objects.get(numero='363')
        self.assertEqual(corrida.produto_id, ctx['prod'].id)
        self.assertEqual(corrida.fornecedor_id, ctx['forn'].id)

    def test_sem_corrida_usa_placeholder(self):
        ctx = _setup_conferencia('A3', corrida='')
        numero_esperado = numero_corrida_sem_rastreabilidade(ctx['prod'].id, ctx['forn'].id)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertTrue(res['aplicado'])
        self.assertFalse(res['pendencias'])
        self.assertEqual(len(res['itens_aplicados']), 1)
        self.assertEqual(res['itens_aplicados'][0]['corrida'], numero_esperado)
        corrida = Corrida.objects.get(numero=numero_esperado)
        self.assertEqual(corrida.produto_id, ctx['prod'].id)
        self.assertEqual(corrida.fornecedor_id, ctx['forn'].id)
        ec = EstoqueCorrida.objects.get(produto=ctx['prod'], corrida=corrida)
        self.assertEqual(ec.saldo, Decimal('10.000'))
        ctx['linha'].refresh_from_db()
        self.assertEqual(ctx['linha'].corrida_estoque_id, corrida.id)

    def test_nao_movimenta_ignora(self):
        ctx = _setup_conferencia('A4', movimenta=False)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'])
        self.assertTrue(res['aplicado'])
        self.assertEqual(len(res['itens_aplicados']), 0)
        self.assertEqual(len(res['itens_ignorados']), 1)
        self.assertEqual(EstoqueCorrida.objects.filter(produto=ctx['prod']).count(), 0)

    def test_fiscal_bloqueado_impede_toda_aplicacao(self):
        ctx = _setup_conferencia('A5')
        RegraFiscalEntrada.objects.filter(nome='R-A5').update(
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        res = aplicar_estoque_fisico_conferencia(ctx['conf'])
        self.assertFalse(res['aplicado'])
        self.assertTrue(res['pendencias'])
        self.assertEqual(EstoqueCorrida.objects.filter(produto=ctx['prod']).count(), 0)

    def test_apto_com_alerta_exige_confirmacao(self):
        ctx = _setup_conferencia('A6', corrida='C-ALERTA')
        RegraFiscalEntrada.objects.filter(nome='R-A6').delete()
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=False)
        self.assertFalse(res['aplicado'])
        self.assertTrue(res['alertas'])
        self.assertFalse(res['pendencias'])

    def test_segunda_chamada_nao_duplica(self):
        ctx = _setup_conferencia('A7')
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        ec = EstoqueCorrida.objects.get(produto=ctx['prod'])
        saldo = ec.saldo
        res2 = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res2['aplicado'])
        ec.refresh_from_db()
        self.assertEqual(ec.saldo, saldo)

    def test_conferencia_ja_aplicada_erro(self):
        ctx = _setup_conferencia('A8')
        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res['aplicado'])
        self.assertTrue(any('já teve estoque' in p['motivo'].lower() for p in res['pendencias']))

    def test_transacional_um_bloqueio_nenhum_aplica(self):
        ctx = _setup_conferencia('A9')
        nf = ctx['nf']
        item2 = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=2,
            prod_json={'CFOP': '5102', 'NCM': '84818099', 'qCom': '5', 'uCom': 'PC'},
            imposto_json={},
        )
        linha2, _ = ctx['conf'].itens.get_or_create(item_nfe_historico=item2)
        linha2.quantidade_nf = Decimal('5')
        linha2.quantidade_estoque_calculada = Decimal('5')
        linha2.corrida = 'C-BLOQ'
        linha2.produto = None
        linha2.status = ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO
        linha2.save()

        res = aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        self.assertFalse(res['aplicado'])
        self.assertEqual(EstoqueCorrida.objects.filter(produto=ctx['prod']).count(), 0)
        ctx['linha'].refresh_from_db()
        linha2.refresh_from_db()
        self.assertIsNone(ctx['linha'].estoque_aplicado_em)
        self.assertIsNone(linha2.estoque_aplicado_em)

    def test_atendimento_marca_fisico_aplicado(self):
        from apps.cadastros.models import Cliente

        ctx = _setup_conferencia('A10')
        cliente = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj())
        ser = NFeSaidaSerializer(
            data={
                'numero': 'NF-ANT-A10',
                'cliente_id': cliente.id,
                'data': '2026-06-01',
                'status': 'Emitida',
                'modo_atendimento_estoque': NFeSaida.ModoAtendimentoEstoque.ANTECIPADO,
                'itens': [{'produto_id': ctx['prod'].id, 'quantidade': '10.000', 'valor': '1.00'}],
            },
        )
        assert ser.is_valid(), ser.errors
        nf_saida = ser.save()
        atend = AtendimentoEstoque.objects.get(nf_saida=nf_saida)
        qtd_antes = atend.quantidade_atendida
        vincular_item_conferencia_a_atendimento(ctx['linha'], atend, Decimal('10.000'))
        atend.refresh_from_db()
        self.assertEqual(atend.quantidade_atendida, qtd_antes + Decimal('10.000'))

        aplicar_estoque_fisico_conferencia(ctx['conf'], confirmar_alertas=True)
        atend.refresh_from_db()
        self.assertTrue(atend.estoque_fisico_aplicado)
        self.assertIsNotNone(atend.estoque_aplicado_em)


class AplicacaoEstoqueAPITests(TestCase):
    def setUp(self):
        self.ctx = _setup_conferencia('API')
        user = get_user_model().objects.create_user('apl_api', 'apl@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user=user)
        self.url = reverse(
            'nf-entrada-hist-importada-aplicar-estoque-conferencia',
            kwargs={'pk': self.ctx['nf'].pk},
        )

    def test_api_post_aplicar(self):
        r = self.client.post(
            self.url,
            {'confirmar_alertas': True, 'observacao': 'Teste'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertTrue(r.json()['aplicado'])


class ResolverCorridaMesmoNumeroProdutosTests(TestCase):
    """Mesmo heat/corrida em produtos diferentes é permitido."""

    def test_mesmo_numero_em_produtos_diferentes(self):
        from apps.fiscal.aplicacao_estoque_conferencia import resolver_ou_criar_corrida

        ctx_a = _setup_conferencia('C1', corrida='W1722549')
        ctx_b = _setup_conferencia('C2', corrida='W1722549')
        # mesmo fornecedor (reusa forn de A no setup B — na prática NF única)
        forn = ctx_a['forn']
        c1 = resolver_ou_criar_corrida(
            produto_id=ctx_a['prod'].id,
            fornecedor_id=forn.id,
            numero_texto='W1722549',
            data_recebimento=date(2026, 6, 1),
        )
        c2 = resolver_ou_criar_corrida(
            produto_id=ctx_b['prod'].id,
            fornecedor_id=forn.id,
            numero_texto='W1722549',
            data_recebimento=date(2026, 6, 1),
        )
        self.assertNotEqual(c1.id, c2.id)
        self.assertEqual(c1.numero, c2.numero)
        self.assertEqual(c1.produto_id, ctx_a['prod'].id)
        self.assertEqual(c2.produto_id, ctx_b['prod'].id)
        self.assertEqual(Corrida.objects.filter(numero='W1722549').count(), 2)