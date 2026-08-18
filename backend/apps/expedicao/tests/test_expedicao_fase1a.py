"""Expedição/Logística Fase 1A — CRUD manual sem efeitos colaterais."""

from __future__ import annotations

import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Fornecedor
from apps.expedicao.models import Expedicao, StatusExpedicao, TipoOperacaoExpedicao
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida, NFeSaida


def _cnpj() -> str:
    h = uuid.uuid4().hex[:12]
    return f'{int(h[:2], 16) % 90 + 10:02d}.{int(h[2:5], 16) % 900 + 100:03d}.{int(h[5:8], 16) % 900 + 100:03d}/0001-{int(h[8:10], 16) % 97:02d}'


class ExpedicaoFase1aTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('exp_user', 'exp@test.com', 'secret')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(razao_social='CLIENTE EXP TEST', cnpj=_cnpj())
        self.fornecedor = Fornecedor.objects.create(razao_social='FORN EXP TEST', cnpj=_cnpj())

    def _payload(self, **extra):
        base = {
            'tipo_operacao': TipoOperacaoExpedicao.RETIRADA_FORNECEDOR,
            'status': StatusExpedicao.RASCUNHO,
            'cliente': self.cliente.pk,
            'fornecedor': self.fornecedor.pk,
            'motorista_nome': 'João Motorista',
            'placa_veiculo': 'ABC1D23',
            'volumes': 2,
            'data_prevista_retirada': '2026-06-20',
            'data_prevista_entrega': '2026-06-22',
            'observacoes': 'Teste expedição',
        }
        base.update(extra)
        return base

    def test_criar_expedicao(self):
        r = self.client.post('/api/expedicoes/', self._payload(), format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        data = r.json()
        self.assertTrue(str(data['codigo']).startswith('EXP-'))
        self.assertEqual(data['status'], StatusExpedicao.RASCUNHO)

    def test_listar_com_filtro_status(self):
        self.client.post('/api/expedicoes/', self._payload(), format='json')
        r = self.client.get('/api/expedicoes/', {'status': StatusExpedicao.RASCUNHO})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.json()['count'], 1)
        self.assertIn('resumo', r.json())

    def test_editar_expedicao(self):
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        r = self.client.patch(
            f"/api/expedicoes/{cri['id']}/",
            {'motorista_nome': 'Maria Motorista', 'volumes': 3},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['motorista_nome'], 'Maria Motorista')
        self.assertEqual(r.json()['volumes'], 3)

    def test_alterar_status(self):
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        r = self.client.post(
            f"/api/expedicoes/{cri['id']}/alterar-status/",
            {'status': StatusExpedicao.MOTORISTA_ENVIADO},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], StatusExpedicao.MOTORISTA_ENVIADO)

    def test_cancelar_expedicao(self):
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        r = self.client.post(
            f"/api/expedicoes/{cri['id']}/cancelar/",
            {'motivo': 'Cliente desistiu'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], StatusExpedicao.CANCELADO)

    def test_requer_autenticacao(self):
        anon = APIClient()
        r = anon.get('/api/expedicoes/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nao_gera_financeiro(self):
        from apps.financeiro.models import TituloFinanceiro

        antes = TituloFinanceiro.objects.count()
        self.client.post('/api/expedicoes/', self._payload(), format='json')
        self.assertEqual(TituloFinanceiro.objects.count(), antes)

    def test_nao_movimenta_estoque(self):
        antes = EstoqueCorrida.objects.count()
        antes_ae = AtendimentoEstoque.objects.count()
        cri = self.client.post('/api/expedicoes/', self._payload(), format='json').json()
        self.client.post(
            f"/api/expedicoes/{cri['id']}/alterar-status/",
            {'status': StatusExpedicao.ENTREGUE_CLIENTE},
            format='json',
        )
        self.assertEqual(EstoqueCorrida.objects.count(), antes)
        self.assertEqual(AtendimentoEstoque.objects.count(), antes_ae)

    def test_nao_altera_nfe(self):
        numeracao_antes = 'NF-E-VOLUME-01'
        nf = NFeSaida.objects.create(
            numero='999001',
            data=date(2026, 6, 1),
            cliente=self.cliente,
            status='AUTORIZADA',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
            numeracao_volumes=numeracao_antes,
        )
        status_antes = nf.status
        chave_antes = nf.chave_acesso
        resposta = self.client.post(
            '/api/expedicoes/',
            self._payload(nfe_saida=nf.pk),
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        cri = resposta.json()
        self.assertEqual(cri['nfe_saida'], nf.pk)
        nf.refresh_from_db()
        self.assertEqual(nf.status, status_antes)
        self.assertEqual(nf.chave_acesso, chave_antes)
        self.assertEqual(nf.numeracao_volumes, numeracao_antes)
        self.assertEqual(Expedicao.objects.filter(nfe_saida=nf).count(), 1)

    def test_resumo_endpoint(self):
        self.client.post('/api/expedicoes/', self._payload(), format='json')
        r = self.client.get('/api/expedicoes/resumo/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('total', r.json())
        self.assertIn('aguardando_separacao', r.json())
