"""ERP 4.0.13.1 — Atendimentos Operacionais (listagem AlocacaoAtendimento)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.services.alocacao_atendimento_service import criar_alocacao_atendimento
from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)
from apps.fiscal.models import AlocacaoAtendimento, AtendimentoEstoque, EstoqueCorrida
from apps.produtos.models import FamiliaProduto, Produto


def _produto(suffix: str | None = None) -> Produto:
    suf = suffix or uuid.uuid4().hex[:6]
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'F{suf}'[:16],
        descricao_base=f'Fam {suf}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Produto {suf}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COD-{suf}',
        unidade='PC',
        ncm='84818099',
    )


class AtendimentosOperacionais40131Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('op40131', 'op@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('40131')
        self.cliente = Cliente.objects.create(
            razao_social='DYNATECH INDUSTRIAS QUIMICAS LTDA',
            cnpj='11.111.111/0001-88',
        )
        self.fornecedor = Fornecedor.objects.create(
            razao_social='FORNECEDOR XYZ LTDA',
            cnpj='22.222.222/0001-88',
        )
        self.pv = PedidoVenda.objects.create(
            numero='PV-20260521-0002',
            cliente=self.cliente,
            data=date(2026, 5, 21),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('100'),
        )
        self.aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('10'),
                'quantidade_atendida': Decimal('4'),
                'quantidade_pendente': Decimal('6'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
                'origem_fisica': OrigemFisica.FORNECEDOR,
                'destino_fisico': DestinoFisico.CLIENTE,
                'fornecedor': self.fornecedor,
            },
            origem_sistema='SISTEMA:CRIAR_ALOCACAO')

    def test_lista_atendimentos_operacionais(self):
        r = self.client.get('/api/atendimentos-operacionais/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertIn('results', data)
        self.assertIn('count', data)
        self.assertGreaterEqual(data['count'], 1)
        row = next(x for x in data['results'] if x['id'] == self.aloc.pk)
        self.assertEqual(row['pedido_venda']['numero'], 'PV-20260521-0002')
        self.assertEqual(row['cliente']['nome'], 'DYNATECH INDUSTRIAS QUIMICAS LTDA')
        self.assertEqual(row['produto']['codigo'], self.produto.codigo_completo)

    def test_search_pv(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'search': 'PV-20260521'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_search_cliente(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'search': 'DYNATECH'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_search_produto(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'search': self.produto.codigo_completo})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_filtro_tipo_atendimento(self):
        r = self.client.get(
            '/api/atendimentos-operacionais/',
            {'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        for row in r.json()['results']:
            self.assertEqual(row['tipo_atendimento'], TipoAtendimentoItem.RETIRADA_FORNECEDOR)

    def test_filtro_status_entrada_fiscal(self):
        r = self.client.get(
            '/api/atendimentos-operacionais/',
            {'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_somente_pendentes(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'somente_pendentes': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_somente_sem_compra(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'somente_sem_compra': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertIn(self.aloc.pk, ids)

    def test_sem_xml_no_retorno(self):
        r = self.client.get('/api/atendimentos-operacionais/')
        body = r.content.decode('utf-8')
        self.assertNotIn('<NFe', body)
        self.assertNotIn('xml_completo', body)

    def test_paginacao(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'page': 1, 'page_size': 20})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['page_size'], 20)
        self.assertIn('total_pages', data)

    def test_listagem_queries_limitadas(self):
        pv2 = PedidoVenda.objects.create(
            numero='PV-40131-B',
            cliente=self.cliente,
            data=date(2026, 5, 22),
        )
        item2 = ItemPedidoVenda.objects.create(
            pedido=pv2,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('50'),
        )
        for _ in range(3):
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': item2,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'quantidade_atendida': Decimal('0'),
                    'quantidade_pendente': Decimal('1'),
                    'tipo_atendimento': TipoAtendimentoItem.NAO_DEFINIDO,
                },
            origem_sistema='SISTEMA:CRIAR_ALOCACAO')
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get('/api/atendimentos-operacionais/', {'page_size': 10})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertLess(len(ctx.captured_queries), 40)

    def test_editar_nao_movimenta_estoque(self):
        antes = EstoqueCorrida.objects.count()
        r = self.client.patch(
            f'/api/alocacoes-atendimento/{self.aloc.pk}/',
            {
                'quantidade_atendida': '5.000',
                'quantidade_pendente': '5.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(EstoqueCorrida.objects.count(), antes)

    def test_editar_nao_gera_financeiro(self):
        from apps.contabil.models import Lancamento

        antes = Lancamento.objects.count()
        self.client.patch(
            f'/api/alocacoes-atendimento/{self.aloc.pk}/',
            {'observacao_operacional': 'teste 40131'},
            format='json',
        )
        self.assertEqual(Lancamento.objects.count(), antes)

    def test_editar_nao_cria_expedicao(self):
        try:
            from apps.expedicao.models import Expedicao
        except ImportError:
            self.skipTest('Módulo expedição não instalado')
        antes = Expedicao.objects.count()
        self.client.patch(
            f'/api/alocacoes-atendimento/{self.aloc.pk}/',
            {'tipo_atendimento': TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE},
            format='json',
        )
        self.assertEqual(Expedicao.objects.count(), antes)

    def test_permissoes_autenticado(self):
        anon = APIClient()
        r = anon.get('/api/atendimentos-operacionais/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dados_antigos_sem_alocacao_nao_quebram(self):
        AtendimentoEstoque.objects.all().delete()
        r = self.client.get('/api/atendimentos-operacionais/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_kpis_endpoint(self):
        r = self.client.get('/api/atendimentos-operacionais/kpis/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertIn('total', data)
        self.assertGreaterEqual(data['total'], 1)
        self.assertIn('conciliacao_entrada_quantitativa', data)
        bloco = data['conciliacao_entrada_quantitativa']
        for key in ('total_origens', 'sem_alocacao', 'parciais', 'conciliadas', 'divergentes'):
            self.assertIn(key, bloco)

    def test_filtro_cte_vinculado_vazio(self):
        r = self.client.get('/api/atendimentos-operacionais/', {'tem_cte_vinculado': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {x['id'] for x in r.json()['results']}
        self.assertNotIn(self.aloc.pk, ids)


class ConciliacaoEntradaQuantitativaS4BBTests(TestCase):
    """S4B-B — KPI quantitativo por item de entrada distinto (sem regravar status)."""

    def setUp(self):
        from django.utils import timezone
        from datetime import datetime

        from apps.fiscal.models import (
            ItemNFeEntradaConferencia,
            ItemNFeEntradaHistoricaImportada,
            NFeEntradaConferencia,
            NFeEntradaHistoricaImportada,
        )

        self.ItemNFeEntradaConferencia = ItemNFeEntradaConferencia
        self.ItemNFeEntradaHistoricaImportada = ItemNFeEntradaHistoricaImportada
        self.NFeEntradaConferencia = NFeEntradaConferencia
        self.NFeEntradaHistoricaImportada = NFeEntradaHistoricaImportada
        self.timezone = timezone
        self.datetime = datetime

        self.user = get_user_model().objects.create_user('s4bb', 's4bb@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('S4BB')
        self.cliente = Cliente.objects.create(razao_social='Cli S4BB', cnpj='55.555.555/0001-55')
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Forn S4BB',
            cnpj='66.666.666/0001-66',
            uf='SP',
        )

    def _origem(self, *, n_item: int, qtd: str = '10') -> tuple:
        from apps.comercial.services.alocacao_entrada_venda_service import alocar_entrada_para_venda

        nf = self.NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + f'S4{n_item}' + 'Z' * 40)[:44],
            numero=f'NE-S4BB-{n_item}',
            serie='1',
            modelo='55',
            dh_emissao=self.timezone.make_aware(self.datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.fornecedor,
            cstat='100',
            tp_amb='1',
        )
        item_nf = self.ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=n_item,
            prod_json={'qCom': qtd, 'uCom': 'PC'},
        )
        conf = self.NFeEntradaConferencia.objects.create(
            nf_entrada_historica=nf,
            status=self.NFeEntradaConferencia.Status.CONFERIDA,
        )
        linha, _ = conf.itens.get_or_create(item_nfe_historico=item_nf)
        linha.produto = self.produto
        linha.quantidade_nf = Decimal(qtd)
        linha.unidade_nf = 'PC'
        linha.quantidade_estoque_calculada = Decimal(qtd)
        linha.unidade_estoque_calculada = 'PC'
        linha.status = self.ItemNFeEntradaConferencia.Status.CONFERIDO
        linha.save()
        return item_nf, linha, alocar_entrada_para_venda

    def _pv_item(self, *, numero: str, qtd: str = '10'):
        pv = PedidoVenda.objects.create(numero=numero, cliente=self.cliente, data=date(2026, 7, 1))
        return ItemPedidoVenda.objects.create(
            pedido=pv,
            produto=self.produto,
            quantidade=Decimal(qtd),
            valor_unitario=Decimal('10'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal(qtd),
        )

    def test_s4bb_origem_integral_uma_venda(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item_nf, linha, alocar = self._origem(n_item=1, qtd='10')
        pvi = self._pv_item(numero='PV-S4BB-1', qtd='10')
        aloc, _ = alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(aloc.status_entrada_fiscal, StatusEntradaFiscal.PENDENTE)
        bloco = calcular_conciliacao_entrada_quantitativa(
            AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=item_nf.pk),
        )
        self.assertEqual(bloco['total_origens'], 1)
        self.assertEqual(bloco['conciliadas'], 1)
        self.assertEqual(bloco['parciais'], 0)
        self.assertEqual(
            bloco['total_origens'],
            bloco['sem_alocacao'] + bloco['parciais'] + bloco['conciliadas'] + bloco['divergentes'],
        )
        aloc.refresh_from_db()
        self.assertEqual(aloc.status_entrada_fiscal, StatusEntradaFiscal.PENDENTE)

    def test_s4bb_origem_parcial(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item_nf, linha, alocar = self._origem(n_item=2, qtd='10')
        pvi = self._pv_item(numero='PV-S4BB-2', qtd='10')
        alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        bloco = calcular_conciliacao_entrada_quantitativa(
            AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=item_nf.pk),
        )
        self.assertEqual(bloco['parciais'], 1)
        self.assertEqual(bloco['conciliadas'], 0)

    def test_s4bb_uma_origem_duas_vendas_conta_uma_vez(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item_nf, linha, alocar = self._origem(n_item=3, qtd='10')
        pvi1 = self._pv_item(numero='PV-S4BB-3a', qtd='6')
        pvi2 = self._pv_item(numero='PV-S4BB-3b', qtd='4')
        alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi1.pk, quantidade=Decimal('6'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi2.pk, quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        qs = AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=item_nf.pk)
        self.assertEqual(qs.count(), 2)
        bloco = calcular_conciliacao_entrada_quantitativa(qs)
        self.assertEqual(bloco['total_origens'], 1)
        self.assertEqual(bloco['conciliadas'], 1)

    def test_s4bb_duas_origens_uma_venda(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item1, linha1, alocar = self._origem(n_item=4, qtd='5')
        item2, linha2, _ = self._origem(n_item=5, qtd='5')
        pvi = self._pv_item(numero='PV-S4BB-45', qtd='10')
        alocar(item_conferencia_id=linha1.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('5'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        alocar(item_conferencia_id=linha2.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('5'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        qs = AlocacaoAtendimento.objects.filter(
            nf_entrada_historica_item_id__in=[item1.pk, item2.pk],
        )
        bloco = calcular_conciliacao_entrada_quantitativa(qs)
        self.assertEqual(bloco['total_origens'], 2)
        self.assertEqual(bloco['conciliadas'], 2)

    def test_s4bb_acima_disponivel_divergente(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item_nf, linha, alocar = self._origem(n_item=6, qtd='10')
        pvi = self._pv_item(numero='PV-S4BB-6', qtd='10')
        aloc, _ = alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        # Força inconsistência residual sem passar pelas validações de alocar.
        AlocacaoAtendimento.objects.filter(pk=aloc.pk).update(quantidade_necessaria=Decimal('12'))
        bloco = calcular_conciliacao_entrada_quantitativa(
            AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=item_nf.pk),
        )
        self.assertEqual(bloco['divergentes'], 1)

    def test_s4bb_desvincular_ultima_remove_origem_do_conjunto(self):
        from apps.comercial.services.alocacao_entrada_venda_service import desvincular_alocacao_entrada_venda
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item_nf, linha, alocar = self._origem(n_item=7, qtd='10')
        pvi = self._pv_item(numero='PV-S4BB-7', qtd='10')
        aloc, _ = alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        desvincular_alocacao_entrada_venda(aloc,
            origem_sistema='SISTEMA:DESVINCULAR_ENTRADA_VENDA')
        bloco = calcular_conciliacao_entrada_quantitativa(
            AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=item_nf.pk),
        )
        # Limitação documentada: sem linhas, origem some (não vira SEM_ALOCACAO).
        self.assertEqual(bloco['total_origens'], 0)
        self.assertEqual(bloco['sem_alocacao'], 0)

    def test_s4bb_tipo_entrada_conciliada_parcial_nao_forca_conciliado(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        item_nf, linha, alocar = self._origem(n_item=8, qtd='10')
        pvi = self._pv_item(numero='PV-S4BB-8', qtd='10')
        aloc, _ = alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('3'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        self.assertEqual(aloc.tipo_atendimento, TipoAtendimentoItem.ENTRADA_CONCILIADA)
        bloco = calcular_conciliacao_entrada_quantitativa(
            AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id=item_nf.pk),
        )
        self.assertEqual(bloco['parciais'], 1)
        self.assertEqual(bloco['conciliadas'], 0)

    def test_s4bb_sem_n_plus_1_para_varias_origens(self):
        from apps.comercial.services.atendimentos_operacionais_service import (
            calcular_conciliacao_entrada_quantitativa,
        )

        def _montar(n: int) -> list[int]:
            ids = []
            for i in range(n):
                item_nf, linha, alocar = self._origem(n_item=100 + n * 10 + i, qtd='4')
                pvi = self._pv_item(numero=f'PV-S4BB-Q{n}-{i}', qtd='4')
                alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('4'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
                ids.append(item_nf.pk)
            return ids

        ids5 = _montar(5)
        qs5 = AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id__in=ids5)
        with self.assertNumQueries(2):
            bloco5 = calcular_conciliacao_entrada_quantitativa(qs5)
        self.assertEqual(bloco5['total_origens'], 5)
        self.assertEqual(bloco5['conciliadas'], 5)
        self.assertEqual(
            bloco5['total_origens'],
            bloco5['sem_alocacao'] + bloco5['parciais'] + bloco5['conciliadas'] + bloco5['divergentes'],
        )

        ids10 = _montar(10)
        qs10 = AlocacaoAtendimento.objects.filter(nf_entrada_historica_item_id__in=ids10)
        with self.assertNumQueries(2):
            bloco10 = calcular_conciliacao_entrada_quantitativa(qs10)
        self.assertEqual(bloco10['total_origens'], 10)
        # Mesmo teto de queries com o dobro de origens (sem N+1).

    def test_s4bb_api_kpis_aditivo_e_sem_efeitos_colaterais(self):
        _, linha, alocar = self._origem(n_item=9, qtd='10')
        pvi = self._pv_item(numero='PV-S4BB-9', qtd='10')
        aloc, _ = alocar(item_conferencia_id=linha.pk, pedido_venda_item_id=pvi.pk, quantidade=Decimal('10'),
            origem_sistema='SISTEMA:CONCILIAR_ENTRADA_VENDA')
        estoque_antes = EstoqueCorrida.objects.count()
        status_antes = aloc.status_entrada_fiscal
        r = self.client.get('/api/atendimentos-operacionais/kpis/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertIn('entradas_conciliadas', data)  # documental preservado
        self.assertIn('conciliacao_entrada_quantitativa', data)
        self.assertGreaterEqual(data['conciliacao_entrada_quantitativa']['conciliadas'], 1)
        aloc.refresh_from_db()
        self.assertEqual(aloc.status_entrada_fiscal, status_antes)
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)

    def test_s4bb_saida_nao_bloqueada_por_entrada(self):
        from apps.fiscal.models import NFeSaida
        from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao

        nf = NFeSaida.objects.create(
            numero='NF-S4BB',
            cliente=self.cliente,
            data=date(2026, 7, 15),
            status='Rascunho',
            valor_total=Decimal('10'),
        )
        texto = ' '.join(validar_nfe_saida_para_emissao(nf).get('mensagens', [])).lower()
        self.assertNotIn('entrada fiscal', texto)
