"""Preparar estoque na conferência NF-e: pedido opcional, produto obrigatório, status automático."""

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
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.conferencia_pedido import calcular_status_operacional_item_conferencia
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _criar_regra_fiscal_entrada_minima() -> RegraFiscalEntrada:
    """Regra genérica válida exigida pelo fluxo de preparar estoque (ERP 4.0.14.10.1+)."""
    regra, created = RegraFiscalEntrada.objects.get_or_create(
        nome='Regra entrada mínima — teste conferência',
        defaults={
            'ativo': True,
            'prioridade': 1,
            'cfop': '5102',
            'cfop_entrada': '1102',
            'tipo_operacao_fiscal': RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            'cst_icms_esperado': '00',
            'severidade': RegraFiscalEntrada.Severidade.ALERTA,
        },
    )
    if not created and not regra.ativo:
        regra.ativo = True
        regra.save(update_fields=['ativo'])
    return regra


def _setup_conferencia(suffix: str, *, com_pedido: bool = True):
    forn = Fornecedor.objects.create(razao_social=f'Forn {suffix}', cnpj=_cnpj())
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    prod = Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suffix}',
        unidade='PC',
        ncm='84818099',
    )
    pedido = PedidoCompra.objects.create(
        numero=f'PC-{suffix}',
        fornecedor=forn,
        data=date(2026, 1, 15),
    )
    item_pc = ItemPedidoCompra.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('10.000'),
        quantidade_negociada=Decimal('10.000'),
        unidade_negociada='PC',
        valor_unitario=Decimal('25.50'),
        valor_total_item=Decimal('255.00'),
    )
    dh = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
    nf = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'35{suffix}'[:44].ljust(44, '0'),
        numero=f'NF{suffix}'[:8],
        serie='1',
        modelo='55',
        dh_emissao=dh,
        valor_total_nf=Decimal('255.00'),
        fornecedor_emitente=forn,
    )
    item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=1,
        prod_json={
            'cProd': f'COD-{suffix}',
            'xProd': f'Produto {suffix}',
            'qCom': '10.000',
            'uCom': 'PC',
            'vUnCom': '25.50',
            'vProd': '255.00',
            'NCM': '84818099',
        },
    )
    item_nf2 = ItemNFeEntradaHistoricaImportada.objects.create(
        nf=nf,
        n_item=2,
        prod_json={
            'cProd': 'OUTRO',
            'xProd': 'Outro item',
            'qCom': '1.000',
            'uCom': 'PC',
            'vUnCom': '1.00',
            'vProd': '1.00',
            'NCM': '84818099',
        },
    )
    conf, _ = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=nf)
    if com_pedido:
        conf.pedido_compra = pedido
        conf.save(update_fields=['pedido_compra'])
    else:
        conf.pedido_compra = None
        conf.save(update_fields=['pedido_compra'])
    linha1, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
    linha2, _ = conf.itens.get_or_create(item_nfe_historico=item_nf2)
    for linha, item_nf_row in ((linha1, item_nf), (linha2, item_nf2)):
        pj = item_nf_row.prod_json or {}
        linha.unidade_nf = str(pj.get('uCom') or 'PC')
        linha.quantidade_nf = Decimal(str(pj.get('qCom') or '0'))
        linha.valor_unitario_nf = Decimal(str(pj.get('vUnCom') or '0'))
        linha.valor_total_nf = Decimal(str(pj.get('vProd') or '0'))
        linha.save(
            update_fields=['unidade_nf', 'quantidade_nf', 'valor_unitario_nf', 'valor_total_nf'],
        )
    user = get_user_model().objects.create_user(f'prep_{suffix}', f'{suffix}@test.com', 'x')
    client = APIClient()
    client.force_authenticate(user)
    url_conf = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': nf.id})
    url_prep = reverse('nf-entrada-hist-importada-preparar-estoque', kwargs={'pk': nf.id})
    return {
        'client': client,
        'url_conf': url_conf,
        'url_prep': url_prep,
        'conf': conf,
        'linha1': linha1,
        'linha2': linha2,
        'prod': prod,
        'pedido': pedido,
        'item_pc': item_pc,
        'nf': nf,
    }


class ConferenciaPrepararEstoqueTests(TestCase):
    def setUp(self):
        _criar_regra_fiscal_entrada_minima()

    def test_preparar_sem_pedido_com_produto_vinculado(self):
        ctx = _setup_conferencia('np', com_pedido=False)
        r_save = ctx['client'].post(
            ctx['url_conf'],
            {
                'pedido_compra_id': None,
                'itens': [
                    {
                        'id': ctx['linha1'].id,
                        'produto_id': ctx['prod'].id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                    {
                        'id': ctx['linha2'].id,
                        'status': 'IGNORADO',
                        'motivo_ignorado': 'Não utilizado nesta NF',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(r_save.status_code, status.HTTP_200_OK)
        ctx['linha1'].refresh_from_db()
        self.assertEqual(ctx['linha1'].status, ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO)

        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)
        ctx['conf'].refresh_from_db()
        self.assertEqual(ctx['conf'].status, NFeEntradaConferencia.Status.PREPARADA)

    def test_preparar_bloqueia_sem_produto_em_linha_nao_ignorada(self):
        ctx = _setup_conferencia('sp', com_pedido=False)
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST)
        pendencias = r_prep.json().get('pendencias') or []
        self.assertTrue(any('produto cadastrado' in p.lower() for p in pendencias))

    def test_preparar_com_pedido_e_item_pedido_vinculado(self):
        ctx = _setup_conferencia('cp')
        r_save = ctx['client'].post(
            ctx['url_conf'],
            {
                'pedido_compra_id': ctx['pedido'].id,
                'itens': [
                    {
                        'id': ctx['linha1'].id,
                        'produto_id': ctx['prod'].id,
                        'item_pedido_compra_id': ctx['item_pc'].id,
                    },
                    {
                        'id': ctx['linha2'].id,
                        'status': 'IGNORADO',
                        'motivo_ignorado': 'Não utilizado nesta NF',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(r_save.status_code, status.HTTP_200_OK)
        ctx['linha1'].refresh_from_db()
        self.assertEqual(ctx['linha1'].status, ItemNFeEntradaConferencia.Status.CONFERIDO)

        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)

    def test_preparar_bloqueia_divergencia_sem_aceite(self):
        ctx = _setup_conferencia('dv')
        ctx['linha2'].status = ItemNFeEntradaConferencia.Status.IGNORADO
        ctx['linha2'].motivo_ignorado = 'N/A'
        ctx['linha2'].save(update_fields=['status', 'motivo_ignorado'])
        ctx['linha1'].produto = ctx['prod']
        ctx['linha1'].item_pedido_compra = ctx['item_pc']
        ctx['linha1'].quantidade_nf = Decimal('99.000')
        ctx['linha1'].save()
        from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia

        aplicar_pos_save_item_conferencia(ctx['linha1'], ctx['conf'])
        ctx['linha1'].refresh_from_db()
        self.assertIn('quantidade_diferente', ctx['linha1'].divergencias)
        self.assertEqual(ctx['linha1'].status, ItemNFeEntradaConferencia.Status.DIVERGENTE)

        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('divergências', ' '.join(r_prep.json().get('pendencias', [])).lower())

    def test_preparar_permite_divergencia_aceita(self):
        ctx = _setup_conferencia('da')
        ctx['linha2'].status = ItemNFeEntradaConferencia.Status.IGNORADO
        ctx['linha2'].motivo_ignorado = 'N/A'
        ctx['linha2'].save(update_fields=['status', 'motivo_ignorado'])
        ctx['linha1'].produto = ctx['prod']
        ctx['linha1'].item_pedido_compra = ctx['item_pc']
        ctx['linha1'].quantidade_nf = Decimal('99.000')
        ctx['linha1'].save()
        from apps.fiscal.conferencia_pedido import aplicar_pos_save_item_conferencia

        aplicar_pos_save_item_conferencia(ctx['linha1'], ctx['conf'])
        ctx['conf'].divergencias_aceitas = True
        ctx['conf'].save(update_fields=['divergencias_aceitas'])

        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)

    def test_status_recalculado_ao_vincular_produto(self):
        ctx = _setup_conferencia('st', com_pedido=False)
        r = ctx['client'].post(
            ctx['url_conf'],
            {
                'pedido_compra_id': None,
                'itens': [{'id': ctx['linha1'].id, 'produto_id': ctx['prod'].id}],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        item = r.json()['itens'][0]
        self.assertEqual(item['status'], 'PRODUTO_VINCULADO')

    def test_linha_ignorada_nao_bloqueia_preparar(self):
        ctx = _setup_conferencia('ig', com_pedido=False)
        r_save = ctx['client'].post(
            ctx['url_conf'],
            {
                'pedido_compra_id': None,
                'itens': [
                    {
                        'id': ctx['linha1'].id,
                        'produto_id': ctx['prod'].id,
                    },
                    {
                        'id': ctx['linha2'].id,
                        'status': 'IGNORADO',
                        'motivo_ignorado': 'Item não aplicável',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(r_save.status_code, status.HTTP_200_OK)
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)

    def test_calcular_status_operacional_helper(self):
        ctx = _setup_conferencia('hl', com_pedido=False)
        linha = ctx['linha1']
        linha.status = ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO
        linha.produto_id = None
        linha.divergencias = []
        self.assertEqual(
            calcular_status_operacional_item_conferencia(linha),
            ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO,
        )
        linha.produto = ctx['prod']
        linha.produto_id = ctx['prod'].id
        self.assertEqual(
            calcular_status_operacional_item_conferencia(linha),
            ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO,
        )
        linha.item_pedido_compra = ctx['item_pc']
        linha.item_pedido_compra_id = ctx['item_pc'].id
        self.assertEqual(
            calcular_status_operacional_item_conferencia(linha),
            ItemNFeEntradaConferencia.Status.CONFERIDO,
        )


class ConferenciaPrepararEstoqueFiscalTests(TestCase):
    def _ctx_fiscal(self, suffix: str):
        ctx = _setup_conferencia(suffix, com_pedido=False)
        item_nf = ctx['linha1'].item_nfe_historico
        pj = dict(item_nf.prod_json or {})
        pj['CFOP'] = '5102'
        pj['NCM'] = '84818099'
        item_nf.prod_json = pj
        item_nf.save(update_fields=['prod_json'])
        ctx['linha2'].status = ItemNFeEntradaConferencia.Status.IGNORADO
        ctx['linha2'].motivo_ignorado = 'Não usado'
        ctx['linha2'].save(update_fields=['status', 'motivo_ignorado'])
        return ctx

    def _salvar_linha1_produto(self, ctx):
        r = ctx['client'].post(
            ctx['url_conf'],
            {
                'pedido_compra_id': None,
                'itens': [
                    {
                        'id': ctx['linha1'].id,
                        'produto_id': ctx['prod'].id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                    {
                        'id': ctx['linha2'].id,
                        'status': 'IGNORADO',
                        'motivo_ignorado': 'Não usado',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return r

    def test_bloqueio_fiscal_impede_preparar(self):
        ctx = self._ctx_fiscal('bf')
        RegraFiscalEntrada.objects.create(
            nome='Bloqueio 5102',
            ativo=True,
            prioridade=10,
            cfop='5102',
            cfop_entrada='1102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
            mensagem_padrao='CFOP bloqueado para estoque',
        )
        self._salvar_linha1_produto(ctx)
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST)
        body = r_prep.json()
        self.assertTrue(body.get('bloqueio_fiscal'))
        texto = ' '.join(body.get('pendencias') or [])
        self.assertIn('Item 1', texto)
        self.assertIn('5102', texto)
        self.assertIn('84818099', texto)
        self.assertIn('Bloqueio 5102', texto)
        self.assertIn('CFOP bloqueado', texto)

    def test_alerta_fiscal_nao_impede_preparar(self):
        ctx = self._ctx_fiscal('af')
        RegraFiscalEntrada.objects.create(
            nome='Alerta 5102',
            ativo=True,
            prioridade=10,
            cfop='5102',
            cfop_entrada='1102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
        )
        self._salvar_linha1_produto(ctx)
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)

    def test_sem_regra_fiscal_impede_preparar(self):
        ctx = self._ctx_fiscal('sr')
        self._salvar_linha1_produto(ctx)
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST, r_prep.content)
        self.assertIn('entrada fiscal', str(r_prep.json()).lower())

    def test_item_ignorado_com_bloqueio_nao_impede_preparar(self):
        ctx = self._ctx_fiscal('igb')
        RegraFiscalEntrada.objects.create(
            nome='Bloqueio 5102',
            ativo=True,
            prioridade=10,
            cfop='5102',
            cfop_entrada='1102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        item_nf1 = ctx['linha1'].item_nfe_historico
        pj1 = dict(item_nf1.prod_json or {})
        pj1['CFOP'] = '6102'
        item_nf1.prod_json = pj1
        item_nf1.save(update_fields=['prod_json'])
        item_nf2 = ctx['linha2'].item_nfe_historico
        pj2 = dict(item_nf2.prod_json or {})
        pj2['CFOP'] = '5102'
        pj2['NCM'] = '84818099'
        item_nf2.prod_json = pj2
        item_nf2.save(update_fields=['prod_json'])
        ctx['linha2'].status = ItemNFeEntradaConferencia.Status.IGNORADO
        ctx['linha2'].motivo_ignorado = 'Linha ignorada com CFOP bloqueado'
        ctx['linha2'].save(update_fields=['status', 'motivo_ignorado'])
        self._salvar_linha1_produto(ctx)
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)

    def test_bloqueio_fiscal_e_validacao_operacional_produto(self):
        ctx = self._ctx_fiscal('bo')
        RegraFiscalEntrada.objects.create(
            nome='Bloqueio 5102',
            ativo=True,
            prioridade=10,
            cfop='5102',
            cfop_entrada='1102',
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.COMPRA,
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST)
        pendencias = r_prep.json().get('pendencias') or []
        self.assertTrue(any('produto cadastrado' in p.lower() for p in pendencias))
