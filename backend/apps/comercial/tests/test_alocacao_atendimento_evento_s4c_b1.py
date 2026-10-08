"""S4C-B1 — trilha append-only AlocacaoAtendimentoEvento."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.comercial.services.alocacao_atendimento_service import (
    AlocacaoAtendimentoErro,
    atualizar_alocacao_atendimento,
    criar_alocacao_atendimento,
    excluir_alocacao_atendimento,
)
from apps.comercial.services.alocacao_atendimento_evento_service import (
    ORIGEM_SISTEMA_CRIAR_ALOCACAO,
)
from apps.comercial.services.alocacao_entrada_venda_service import (
    alocar_entrada_para_venda,
)
from apps.fiscal.serializers import AlocacaoAtendimentoEventoSerializer
from apps.fiscal.modelo_operacional import StatusEntradaFiscal, TipoAtendimentoItem
from apps.fiscal.models import (
    AlocacaoAtendimento,
    AlocacaoAtendimentoEvento,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(suffix: str) -> Produto:
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'AE{suffix}'[:16],
        descricao_base=f'Fam {suffix}',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao=f'Prod {suffix}',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'AE-{suffix}',
        unidade='PC',
        ncm='84818099',
    )


_PROIBIDOS = (
    'xml',
    'chave_acesso',
    'chave_nfe',
    'cnpj',
    'cpf',
    'razao_social',
    'email',
    'observacao_operacional',
    'password',
    'token',
    'secret',
)


class AlocacaoAtendimentoEventoModeloTests(TestCase):
    def test_evento_imutavel_apos_criacao(self):
        user = get_user_model().objects.create_user('evt_imm', 'i@t.com', 'x')
        ev = AlocacaoAtendimentoEvento.objects.create(
            evento=AlocacaoAtendimentoEvento.Evento.CRIADA,
            alocacao=None,
            alocacao_id_snapshot=999001,
            ator=user,
            ator_id_snapshot=user.pk,
            ator_rotulo_snapshot=user.username[:64],
            antes={},
            depois={'id': 999001},
        )
        ev.motivo = 'alterar'
        with self.assertRaises(ValidationError):
            ev.save()
        with self.assertRaises(ValidationError):
            ev.delete()


class AlocacaoAtendimentoEventoEscritaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('evt_w', 'w@t.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('W1')
        self.cliente = Cliente.objects.create(razao_social='Cli EVT', cnpj=_cnpj())
        self.pv = PedidoVenda.objects.create(
            numero='PV-EVT-W',
            cliente=self.cliente,
            data=date(2026, 7, 20),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('20'),
            valor_unitario=Decimal('10'),
        )

    def _payload_crud(self, **over):
        base = {
            'produto_id': self.produto.pk,
            'pedido_venda_item_id': self.item_pv.pk,
            'quantidade_necessaria': '3.000',
            'quantidade_atendida': '0.000',
            'quantidade_pendente': '3.000',
            'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
        }
        base.update(over)
        return base

    def _assert_payload_limpo(self, payload: dict):
        blob = str(payload).lower()
        for proibido in _PROIBIDOS:
            self.assertNotIn(proibido, blob)

    def test_01_create_crud_com_ator_gera_criada(self):
        r = self.client.post('/api/alocacoes-atendimento/', self._payload_crud(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        evs = AlocacaoAtendimentoEvento.objects.filter(alocacao_id_snapshot=r.data['id'])
        self.assertEqual(evs.count(), 1)
        ev = evs.get()
        self.assertEqual(ev.evento, AlocacaoAtendimentoEvento.Evento.CRIADA)
        self.assertEqual(ev.ator_id, self.user.pk)
        self.assertEqual(ev.ator_id_snapshot, self.user.pk)
        self.assertEqual(ev.ator_rotulo_snapshot, self.user.username)
        self._assert_payload_limpo(ev.depois)

    def test_02_update_com_alteracao_real_gera_atualizada(self):
        cri = self.client.post('/api/alocacoes-atendimento/', self._payload_crud(), format='json')
        pk = cri.data['id']
        patch = self.client.patch(
            f'/api/alocacoes-atendimento/{pk}/',
            {'quantidade_necessaria': '4.000', 'quantidade_pendente': '4.000'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)
        evs = list(
            AlocacaoAtendimentoEvento.objects.filter(alocacao_id_snapshot=pk).order_by('id'),
        )
        self.assertEqual(len(evs), 2)
        self.assertEqual(evs[1].evento, AlocacaoAtendimentoEvento.Evento.ATUALIZADA)
        self.assertIn('campos_alterados', evs[1].depois)
        self.assertIn('quantidade_necessaria', evs[1].depois['campos_alterados'])

    def test_03_update_sem_mudanca_efetiva_nao_gera_evento_falso(self):
        cri = self.client.post('/api/alocacoes-atendimento/', self._payload_crud(), format='json')
        pk = cri.data['id']
        # observacao fora do allowlist — não deve gerar ATUALIZADA
        patch = self.client.patch(
            f'/api/alocacoes-atendimento/{pk}/',
            {'observacao_operacional': 'somente texto livre'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AlocacaoAtendimentoEvento.objects.filter(alocacao_id_snapshot=pk).count(),
            1,
        )
        self.assertEqual(
            AlocacaoAtendimentoEvento.objects.filter(
                alocacao_id_snapshot=pk,
                evento=AlocacaoAtendimentoEvento.Evento.ATUALIZADA,
            ).count(),
            0,
        )

    def test_08_delete_crud_gera_excluida_e_permanece(self):
        cri = self.client.post('/api/alocacoes-atendimento/', self._payload_crud(), format='json')
        pk = cri.data['id']
        del_r = self.client.delete(f'/api/alocacoes-atendimento/{pk}/')
        self.assertEqual(del_r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AlocacaoAtendimento.objects.filter(pk=pk).exists())
        ev = AlocacaoAtendimentoEvento.objects.get(
            alocacao_id_snapshot=pk,
            evento=AlocacaoAtendimentoEvento.Evento.EXCLUIDA,
        )
        self.assertIsNone(ev.alocacao_id)
        self.assertEqual(ev.ator_id_snapshot, self.user.pk)

    def test_09_chamada_sistema_gera_ator_null_e_rotulo_sistema(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_pendente': Decimal('2'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=None,
            origem_sistema=ORIGEM_SISTEMA_CRIAR_ALOCACAO,
        )
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=aloc.pk)
        self.assertIsNone(ev.ator_id)
        self.assertIsNone(ev.ator_id_snapshot)
        self.assertEqual(ev.ator_rotulo_snapshot, ORIGEM_SISTEMA_CRIAR_ALOCACAO)
        self.assertNotIn('@', ev.ator_rotulo_snapshot)
        self.assertNotIn('email', ev.ator_rotulo_snapshot.lower())

    def test_10_usuario_removido_preserva_snapshot(self):
        outro = get_user_model().objects.create_user('evt_del', 'd@t.com', 'x')
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'quantidade_pendente': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=outro,
        )
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=aloc.pk)
        uid = outro.pk
        rotulo = outro.username
        outro.delete()
        ev.refresh_from_db()
        self.assertIsNone(ev.ator_id)
        self.assertEqual(ev.ator_id_snapshot, uid)
        self.assertEqual(ev.ator_rotulo_snapshot, rotulo)

    def test_11_falha_na_criacao_do_evento_reverte_mutacao(self):
        with patch(
            'apps.comercial.services.alocacao_atendimento_evento_service.AlocacaoAtendimentoEvento.objects.create',
            side_effect=RuntimeError('falha evento'),
        ):
            with self.assertRaises(RuntimeError):
                criar_alocacao_atendimento(
                    {
                        'pedido_venda_item': self.item_pv,
                        'produto': self.produto,
                        'quantidade_necessaria': Decimal('1'),
                        'quantidade_pendente': Decimal('1'),
                        'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                    },
                    ator=self.user,
                )
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)
        self.assertEqual(AlocacaoAtendimentoEvento.objects.count(), 0)

    def test_12_falha_no_delete_reverte_evento_pre_delete(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'quantidade_pendente': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=self.user,
        )
        pk = aloc.pk
        with patch.object(AlocacaoAtendimento, 'delete', side_effect=RuntimeError('falha delete')):
            with self.assertRaises(RuntimeError):
                excluir_alocacao_atendimento(aloc, ator=self.user)
        self.assertTrue(AlocacaoAtendimento.objects.filter(pk=pk).exists())
        self.assertEqual(
            AlocacaoAtendimentoEvento.objects.filter(
                alocacao_id_snapshot=pk,
                evento=AlocacaoAtendimentoEvento.Evento.EXCLUIDA,
            ).count(),
            0,
        )


class AlocacaoAtendimentoEventoConciliacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('evt_c', 'c@t.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('C1')
        self.cliente = Cliente.objects.create(razao_social='Cli EVT C', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn EVT', cnpj=_cnpj(), uf='SP')
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'EVT' + 'Z' * 40)[:44],
            numero='NE-EVT',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.fornecedor,
            cstat='100',
            tp_amb='1',
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'qCom': '10.000', 'uCom': 'PC'},
        )
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.CONFERIDA,
        )
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)
        self.linha.produto = self.produto
        self.linha.quantidade_estoque_calculada = Decimal('10.000')
        self.linha.unidade_estoque_calculada = 'PC'
        self.linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        self.linha.save()
        self.pv = PedidoVenda.objects.create(
            numero='PV-EVT-C',
            cliente=self.cliente,
            data=date(2026, 7, 1),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('10'),
            valor_unitario=Decimal('50'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('10'),
        )

    def test_04_upsert_criado_gera_unico_conciliada(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '4.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        pk = r.data['alocacao']['id']
        evs = AlocacaoAtendimentoEvento.objects.filter(alocacao_id_snapshot=pk)
        self.assertEqual(evs.count(), 1)
        ev = evs.get()
        self.assertEqual(ev.evento, AlocacaoAtendimentoEvento.Evento.CONCILIADA)
        self.assertEqual(ev.depois.get('acao_upsert'), 'criado')
        self.assertEqual(ev.ator_id, self.user.pk)
        self.assertEqual(ev.nf_entrada_historica_item_id_snapshot, self.item_nf.pk)
        self.assertEqual(ev.pedido_venda_item_id_snapshot, self.item_pv.pk)

    def test_05_upsert_atualizado_gera_unico_conciliada(self):
        alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('3'),
            ator=self.user,
        )
        r = self.client.post(
            '/api/alocacoes-atendimento/alocar-entrada-venda/',
            {
                'item_conferencia_id': self.linha.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade': '5.000',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['acao'], 'atualizado')
        pk = r.data['alocacao']['id']
        conc = AlocacaoAtendimentoEvento.objects.filter(
            alocacao_id_snapshot=pk,
            evento=AlocacaoAtendimentoEvento.Evento.CONCILIADA,
        )
        self.assertEqual(conc.count(), 2)
        self.assertEqual(conc.order_by('-id').first().depois.get('acao_upsert'), 'atualizado')
        self.assertEqual(
            AlocacaoAtendimentoEvento.objects.filter(alocacao_id_snapshot=pk).exclude(
                evento=AlocacaoAtendimentoEvento.Evento.CONCILIADA,
            ).count(),
            0,
        )

    def test_crud_create_fase1_nao_duplica_criada(self):
        """Create CRUD com hist+PV delega e emite só CONCILIADA."""
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'nf_entrada_historica_item': self.item_nf,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_atendida': Decimal('2'),
                'quantidade_pendente': Decimal('0'),
            },
            ator=self.user,
        )
        tipos = list(
            AlocacaoAtendimentoEvento.objects.filter(alocacao_id_snapshot=aloc.pk).values_list(
                'evento',
                flat=True,
            ),
        )
        self.assertEqual(tipos, [AlocacaoAtendimentoEvento.Evento.CONCILIADA])

    def test_06_ajuste_quantitativo_gera_quantidade_ajustada(self):
        aloc, _ = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('4'),
            ator=self.user,
        )
        r = self.client.patch(
            f'/api/alocacoes-atendimento/{aloc.pk}/quantidade-entrada-venda/',
            {'quantidade': '6.000'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        ev = AlocacaoAtendimentoEvento.objects.get(
            alocacao_id_snapshot=aloc.pk,
            evento=AlocacaoAtendimentoEvento.Evento.QUANTIDADE_AJUSTADA,
        )
        self.assertEqual(ev.depois['quantidade_necessaria'], '6.000')
        self.assertEqual(ev.ator_id, self.user.pk)

    def test_07_desvinculacao_gera_desvinculada_e_permanece(self):
        aloc, _ = alocar_entrada_para_venda(
            item_conferencia_id=self.linha.pk,
            pedido_venda_item_id=self.item_pv.pk,
            quantidade=Decimal('2'),
            ator=self.user,
        )
        pk = aloc.pk
        hist_id = aloc.nf_entrada_historica_item_id
        r = self.client.post(f'/api/alocacoes-atendimento/{pk}/desvincular-entrada-venda/')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(AlocacaoAtendimento.objects.filter(pk=pk).exists())
        ev = AlocacaoAtendimentoEvento.objects.get(
            alocacao_id_snapshot=pk,
            evento=AlocacaoAtendimentoEvento.Evento.DESVINCULADA,
        )
        self.assertIsNone(ev.alocacao_id)
        self.assertEqual(ev.nf_entrada_historica_item_id_snapshot, hist_id)


class AlocacaoAtendimentoEventoApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('evt_api', 'a@t.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('A1')
        self.cliente = Cliente.objects.create(razao_social='Cli API', cnpj=_cnpj())
        self.pv = PedidoVenda.objects.create(
            numero='PV-EVT-A',
            cliente=self.cliente,
            data=date(2026, 7, 21),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('5'),
            valor_unitario=Decimal('10'),
        )
        self.aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_pendente': Decimal('2'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=self.user,
        )

    def test_13_api_nao_aceita_mutacoes(self):
        url = '/api/alocacoes-atendimento-eventos/'
        self.assertEqual(self.client.post(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        detail = f'{url}{AlocacaoAtendimentoEvento.objects.first().pk}/'
        self.assertEqual(self.client.put(detail, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.patch(detail, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(detail).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_14_usuario_nao_autenticado_nao_acessa(self):
        anon = APIClient()
        r = anon.get('/api/alocacoes-atendimento-eventos/')
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_15_filtros_por_snapshots(self):
        r = self.client.get(
            '/api/alocacoes-atendimento-eventos/',
            {'alocacao_id_snapshot': self.aloc.pk},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data['results'] if isinstance(r.data, dict) and 'results' in r.data else r.data
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(all(x['alocacao_id_snapshot'] == self.aloc.pk for x in results))

        r2 = self.client.get(
            '/api/alocacoes-atendimento-eventos/',
            {'pedido_venda_item_id_snapshot': self.item_pv.pk},
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        results2 = r2.data['results'] if isinstance(r2.data, dict) and 'results' in r2.data else r2.data
        self.assertGreaterEqual(len(results2), 1)

        # Filtro por origem histórica (evento de conciliação)
        from apps.fiscal.models import ItemNFeEntradaHistoricaImportada, NFeEntradaHistoricaImportada
        from apps.cadastros.models import Fornecedor

        forn = Fornecedor.objects.create(razao_social='Forn Filt', cnpj=_cnpj(), uf='SP')
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'FLT' + 'Z' * 40)[:44],
            numero='NE-FLT',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 2, 10, 0)),
            valor_total_nf=Decimal('10'),
            fornecedor_emitente=forn,
            cstat='100',
            tp_amb='1',
        )
        hist = ItemNFeEntradaHistoricaImportada.objects.create(nf=nf, n_item=1, prod_json={})
        AlocacaoAtendimentoEvento.objects.create(
            evento=AlocacaoAtendimentoEvento.Evento.CONCILIADA,
            alocacao_id_snapshot=888001,
            ator_rotulo_snapshot='SISTEMA',
            nf_entrada_historica_item_id_snapshot=hist.pk,
            pedido_venda_item_id_snapshot=self.item_pv.pk,
            antes={},
            depois={'acao_upsert': 'criado'},
        )
        r3 = self.client.get(
            '/api/alocacoes-atendimento-eventos/',
            {'nf_entrada_historica_item_id_snapshot': hist.pk},
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        results3 = r3.data['results'] if isinstance(r3.data, dict) and 'results' in r3.data else r3.data
        self.assertTrue(all(x['nf_entrada_historica_item_id_snapshot'] == hist.pk for x in results3))
        self.assertGreaterEqual(len(results3), 1)

    def test_16_payload_sem_dados_proibidos(self):
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=self.aloc.pk)
        for payload in (ev.antes, ev.depois):
            blob = str(payload).lower()
            for proibido in _PROIBIDOS:
                self.assertNotIn(proibido, blob)
        self.assertNotIn('email', ev.ator_rotulo_snapshot.lower())
        self.assertNotIn('@', ev.ator_rotulo_snapshot)

    def test_historico_apos_exclusao_consultavel(self):
        pk = self.aloc.pk
        excluir_alocacao_atendimento(self.aloc, ator=self.user)
        r = self.client.get(
            '/api/alocacoes-atendimento-eventos/',
            {'alocacao_id_snapshot': pk},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        results = r.data['results'] if isinstance(r.data, dict) and 'results' in r.data else r.data
        eventos = {x['evento'] for x in results}
        self.assertIn(AlocacaoAtendimentoEvento.Evento.EXCLUIDA, eventos)
        self.assertIn(AlocacaoAtendimentoEvento.Evento.CRIADA, eventos)


class AlocacaoAtendimentoEventoR2IntegridadeTests(TestCase):
    """S4C-B1 R2 — origem explícita, troca de PK, append-only, serializer."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('evt_r2', 'r2@t.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.produto = _produto('R2')
        self.cliente = Cliente.objects.create(razao_social='Cli R2', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='Forn R2', cnpj=_cnpj(), uf='SP')
        self.pv = PedidoVenda.objects.create(
            numero='PV-EVT-R2',
            cliente=self.cliente,
            data=date(2026, 7, 22),
        )
        self.item_pv = ItemPedidoVenda.objects.create(
            pedido=self.pv,
            produto=self.produto,
            quantidade=Decimal('20'),
            valor_unitario=Decimal('10'),
            unidade_estoque_calculada='PC',
            quantidade_estoque_calculada=Decimal('20'),
        )
        self.nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + 'R2A' + 'Z' * 40)[:44],
            numero='NE-R2',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.fornecedor,
            cstat='100',
            tp_amb='1',
        )
        self.item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={'qCom': '20.000', 'uCom': 'PC'},
        )
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.CONFERIDA,
        )
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=self.item_nf)
        self.linha.produto = self.produto
        self.linha.quantidade_estoque_calculada = Decimal('20.000')
        self.linha.unidade_estoque_calculada = 'PC'
        self.linha.status = ItemNFeEntradaConferencia.Status.CONFERIDO
        self.linha.save()

    def test_r2_01_sistema_sem_origem_e_rejeitado_sem_mutacao(self):
        with self.assertRaises(AlocacaoAtendimentoErro):
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': self.item_pv,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'quantidade_pendente': Decimal('1'),
                    'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                },
                ator=None,
            )
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)
        self.assertEqual(AlocacaoAtendimentoEvento.objects.count(), 0)

        with self.assertRaises(AlocacaoAtendimentoErro):
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': self.item_pv,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'quantidade_pendente': Decimal('1'),
                    'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                },
                ator=None,
                origem_sistema='   ',
            )
        self.assertEqual(AlocacaoAtendimento.objects.count(), 0)

    def test_r2_02_sistema_com_origem_explicita_e_auditado(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'quantidade_pendente': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=None,
            origem_sistema=ORIGEM_SISTEMA_CRIAR_ALOCACAO,
        )
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=aloc.pk)
        self.assertIsNone(ev.ator_id)
        self.assertEqual(ev.ator_rotulo_snapshot, ORIGEM_SISTEMA_CRIAR_ALOCACAO)

    def test_r2_03_request_user_prevalece_sobre_origem(self):
        r = self.client.post(
            '/api/alocacoes-atendimento/',
            {
                'produto_id': self.produto.pk,
                'pedido_venda_item_id': self.item_pv.pk,
                'quantidade_necessaria': '1.000',
                'quantidade_pendente': '1.000',
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                'status_entrada_fiscal': StatusEntradaFiscal.PENDENTE,
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=r.data['id'])
        self.assertEqual(ev.ator_id, self.user.pk)
        self.assertEqual(ev.ator_rotulo_snapshot, self.user.username)
        self.assertNotEqual(ev.ator_rotulo_snapshot, ORIGEM_SISTEMA_CRIAR_ALOCACAO)

    def test_r2_04_troca_de_pk_gera_unico_conciliada_rastreavel(self):
        aloc_old = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_pendente': Decimal('2'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=self.user,
        )
        old_pk = aloc_old.pk
        antes_count = AlocacaoAtendimentoEvento.objects.filter(
            evento=AlocacaoAtendimentoEvento.Evento.CONCILIADA,
        ).count()

        aloc_final = atualizar_alocacao_atendimento(
            aloc_old,
            {
                'nf_entrada_historica_item': self.item_nf,
                'pedido_venda_item': self.item_pv,
                'quantidade_necessaria': Decimal('2'),
                'quantidade_atendida': Decimal('2'),
                'quantidade_pendente': Decimal('0'),
            },
            ator=self.user,
        )
        self.assertNotEqual(aloc_final.pk, old_pk)
        self.assertFalse(AlocacaoAtendimento.objects.filter(pk=old_pk).exists())
        self.assertTrue(AlocacaoAtendimento.objects.filter(pk=aloc_final.pk).exists())

        conc = AlocacaoAtendimentoEvento.objects.filter(
            evento=AlocacaoAtendimentoEvento.Evento.CONCILIADA,
        )
        self.assertEqual(conc.count(), antes_count + 1)
        ev = conc.order_by('-id').first()
        self.assertEqual(ev.alocacao_id_snapshot, aloc_final.pk)
        self.assertEqual(ev.depois.get('acao_upsert'), 'substituido')
        self.assertEqual(ev.depois.get('alocacao_id_anterior'), old_pk)
        self.assertEqual(ev.antes.get('id'), old_pk)
        self.assertEqual(ev.depois.get('id'), aloc_final.pk)
        self.assertEqual(
            AlocacaoAtendimentoEvento.objects.filter(
                alocacao_id_snapshot=old_pk,
                evento=AlocacaoAtendimentoEvento.Evento.EXCLUIDA,
            ).count(),
            0,
        )
        blob = str(ev.antes) + str(ev.depois)
        for proibido in _PROIBIDOS:
            self.assertNotIn(proibido, blob.lower())

    def test_r2_05_save_pos_criacao_bloqueado(self):
        ev = AlocacaoAtendimentoEvento.objects.create(
            evento=AlocacaoAtendimentoEvento.Evento.CRIADA,
            alocacao_id_snapshot=1,
            ator_rotulo_snapshot='SISTEMA:CRIAR_ALOCACAO',
            antes={},
            depois={},
        )
        ev.motivo = 'x'
        with self.assertRaises(ValidationError):
            ev.save()

    def test_r2_06_delete_instancia_bloqueado(self):
        ev = AlocacaoAtendimentoEvento.objects.create(
            evento=AlocacaoAtendimentoEvento.Evento.CRIADA,
            alocacao_id_snapshot=2,
            ator_rotulo_snapshot='SISTEMA:CRIAR_ALOCACAO',
            antes={},
            depois={},
        )
        with self.assertRaises(ValidationError):
            ev.delete()

    def test_r2_07_queryset_update_permanece_possivel_orm(self):
        """Documenta: QuerySet.update NÃO é bloqueado (necessário p/ SET_NULL)."""
        ev = AlocacaoAtendimentoEvento.objects.create(
            evento=AlocacaoAtendimentoEvento.Evento.CRIADA,
            alocacao_id_snapshot=3,
            ator_rotulo_snapshot='SISTEMA:CRIAR_ALOCACAO',
            antes={},
            depois={},
        )
        updated = AlocacaoAtendimentoEvento.objects.filter(pk=ev.pk).update(motivo='via-qs')
        self.assertEqual(updated, 1)
        ev.refresh_from_db()
        self.assertEqual(ev.motivo, 'via-qs')

    def test_r2_08_queryset_delete_permanece_possivel_orm(self):
        """Documenta: QuerySet.delete NÃO é bloqueado; API/admin não o expõem."""
        ev = AlocacaoAtendimentoEvento.objects.create(
            evento=AlocacaoAtendimentoEvento.Evento.CRIADA,
            alocacao_id_snapshot=4,
            ator_rotulo_snapshot='SISTEMA:CRIAR_ALOCACAO',
            antes={},
            depois={},
        )
        deleted, _ = AlocacaoAtendimentoEvento.objects.filter(pk=ev.pk).delete()
        self.assertEqual(deleted, 1)
        self.assertFalse(AlocacaoAtendimentoEvento.objects.filter(pk=ev.pk).exists())

    def test_r2_09_set_null_alocacao_funciona(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'quantidade_pendente': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=self.user,
        )
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=aloc.pk)
        self.assertEqual(ev.alocacao_id, aloc.pk)
        snap = ev.alocacao_id_snapshot
        aloc.delete()
        ev.refresh_from_db()
        self.assertIsNone(ev.alocacao_id)
        self.assertEqual(ev.alocacao_id_snapshot, snap)

    def test_r2_10_set_null_ator_funciona(self):
        outro = get_user_model().objects.create_user('evt_r2b', 'r2b@t.com', 'x')
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'quantidade_pendente': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=outro,
        )
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=aloc.pk)
        uid = outro.pk
        rotulo = outro.username
        outro.delete()
        ev.refresh_from_db()
        self.assertIsNone(ev.ator_id)
        self.assertEqual(ev.ator_id_snapshot, uid)
        self.assertEqual(ev.ator_rotulo_snapshot, rotulo)

    def test_r2_11_api_mutadora_405(self):
        url = '/api/alocacoes-atendimento-eventos/'
        self.assertEqual(self.client.post(url, {}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_r2_12_serializer_somente_campos_autorizados(self):
        aloc = criar_alocacao_atendimento(
            {
                'pedido_venda_item': self.item_pv,
                'produto': self.produto,
                'quantidade_necessaria': Decimal('1'),
                'quantidade_pendente': Decimal('1'),
                'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
            },
            ator=self.user,
        )
        ev = AlocacaoAtendimentoEvento.objects.get(alocacao_id_snapshot=aloc.pk)
        data = AlocacaoAtendimentoEventoSerializer(ev).data
        esperados = {
            'id',
            'evento',
            'alocacao_id_snapshot',
            'ator_id_snapshot',
            'ator_rotulo_snapshot',
            'nf_entrada_historica_item_id_snapshot',
            'pedido_venda_item_id_snapshot',
            'antes',
            'depois',
            'motivo',
            'criado_em',
        }
        self.assertEqual(set(data.keys()), esperados)
        self.assertNotIn('ator', data)
        self.assertNotIn('alocacao', data)
        self.assertNotIn('email', str(data).lower())

    def test_r2_13_admin_nao_registrado(self):
        from django.contrib import admin

        self.assertFalse(admin.site.is_registered(AlocacaoAtendimentoEvento))

    def test_r2_14_unico_writer_publico_de_eventos(self):
        with patch(
            'apps.comercial.services.alocacao_atendimento_evento_service.AlocacaoAtendimentoEvento.objects.create',
            wraps=AlocacaoAtendimentoEvento.objects.create,
        ) as mocked:
            criar_alocacao_atendimento(
                {
                    'pedido_venda_item': self.item_pv,
                    'produto': self.produto,
                    'quantidade_necessaria': Decimal('1'),
                    'quantidade_pendente': Decimal('1'),
                    'tipo_atendimento': TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                },
                ator=self.user,
            )
            self.assertGreaterEqual(mocked.call_count, 1)
        with self.assertRaises(AlocacaoAtendimentoErro):
            alocar_entrada_para_venda(
                item_conferencia_id=self.linha.pk,
                pedido_venda_item_id=self.item_pv.pk,
                quantidade=Decimal('1'),
                ator=None,
            )
