"""Testes ERP 4.0.7 — paginação nos módulos restantes."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Colaborador, Empresa, Fornecedor, Transportadora
from apps.comercial.models import PedidoCompra, Proposta
from apps.corridas.models import Corrida
from apps.fiscal.models import (
    AtendimentoEstoque,
    CTeEntrada,
    CTeHistoricoImportado,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
)
from apps.produtos.models import Produto
from apps.qualidade.models import CertificadoQualidade
from apps.regras_fiscais.models import RegraFiscal


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _chave(prefix: str = '35') -> str:
    base = f'{prefix}{uuid.uuid4().int % 10**42:042d}'
    return base[:44]


class Paginacao407Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pag407', 'pag407@test.com', 'x')
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        hoje = timezone.localdate()
        agora = timezone.now()

        self.empresa = Empresa.objects.create(razao_social='Empresa 407', cnpj=_cnpj(), uf='SC')
        self.cliente = Cliente.objects.create(razao_social='Cliente 407', cnpj=_cnpj(), uf='SC')
        self.fornecedor = Fornecedor.objects.create(razao_social='Fornecedor 407', cnpj=_cnpj(), uf='SC')
        self.transportadora = Transportadora.objects.create(
            razao_social='Transportadora 407', cnpj=_cnpj(), uf='SC',
        )
        self.produto = Produto.objects.create(codigo_completo='P407', descricao='Produto 407', material='Aço')
        self.nf_saida = NFeSaida.objects.create(
            numero='NF407', cliente=self.cliente, data=hoje, status='RASCUNHO', valor_total=Decimal('100'),
        )

        for i in range(3):
            Fornecedor.objects.create(razao_social=f'Forn Pag {i}', cnpj=_cnpj(), uf='SC', cidade=f'Cidade {i}')
            Transportadora.objects.create(razao_social=f'Trans Pag {i}', cnpj=_cnpj(), uf='SC')
            Colaborador.objects.create(nome=f'Colab Pag {i}', email=f'colab{i}@test.com', ativo=True)
            Proposta.objects.create(
                numero=f'PROP-407-{i:02d}',
                cliente=self.cliente,
                data=hoje,
                validade=hoje,
                status='ABERTA' if i == 0 else 'APROVADA',
            )
            PedidoCompra.objects.create(
                numero=f'PC-407-{i:02d}',
                fornecedor=self.fornecedor,
                data=hoje,
                status='ABERTO',
            )
            NFeEntrada.objects.create(
                numero=f'NE407-{i}',
                fornecedor=self.fornecedor,
                data=hoje,
            )
            RegraFiscal.objects.create(
                ncm='73079300',
                uf_origem='SC',
                uf_destino='SC',
                operacao='Saída' if i % 2 == 0 else 'Entrada',
                cfop='5102',
            )
            CTeEntrada.objects.create(
                numero=f'CTE407-{i}',
                transportadora=self.transportadora,
                tomador=self.empresa,
                data=hoje,
            )
            Corrida.objects.create(
                numero=f'CORR407-{i}',
                produto=self.produto,
                fornecedor=self.fornecedor,
                data_recebimento=hoje,
            )
            NFeEntradaHistoricaImportada.objects.create(
                chave_acesso=_chave('35'),
                numero=f'{100 + i}',
                dh_emissao=agora,
                valor_total_nf=Decimal('50'),
            )
            CTeHistoricoImportado.objects.create(
                chave_acesso=_chave('57'),
                numero=f'{200 + i}',
                dh_emissao=agora,
                valor_total_servico=Decimal('30'),
            )
            CertificadoQualidade.objects.create(numero=f'CQ407-{i}', status='rascunho')

        AtendimentoEstoque.objects.create(
            nf_saida=self.nf_saida,
            produto=self.produto,
            quantidade_comprometida=Decimal('1'),
            status='PENDENTE',
        )

    def _assert_paginated(self, url: str, params=None):
        p = {'page': 1, 'page_size': 20}
        if params:
            p.update(params)
        resp = self.client.get(url, p)
        self.assertEqual(resp.status_code, 200, resp.content[:500])
        data = resp.json()
        self.assertIn('count', data)
        self.assertIn('results', data)
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['page_size'], 20)
        self.assertLessEqual(len(data['results']), 20)
        return data

    def test_fornecedores_retorna_paginacao(self):
        data = self._assert_paginated('/api/fornecedores/')
        self.assertGreaterEqual(data['count'], 4)

    def test_transportadoras_retorna_paginacao(self):
        self._assert_paginated('/api/transportadoras/')

    def test_colaboradores_retorna_paginacao(self):
        self._assert_paginated('/api/colaboradores/')

    def test_propostas_retorna_paginacao(self):
        self._assert_paginated('/api/propostas/')

    def test_pedidos_compra_retorna_paginacao(self):
        self._assert_paginated('/api/pedidos-compra/')

    def test_nf_entrada_retorna_paginacao(self):
        self._assert_paginated('/api/nf-entradas/')

    def test_nf_entrada_historica_retorna_paginacao(self):
        self._assert_paginated('/api/nf-entradas-historicas-importadas/')

    def test_regras_fiscais_retorna_paginacao(self):
        self._assert_paginated('/api/regras-fiscais/')

    def test_cte_entrada_retorna_paginacao(self):
        self._assert_paginated('/api/cte-entradas/')

    def test_cte_historico_retorna_paginacao(self):
        self._assert_paginated('/api/cte-historicos-importados/')

    def test_corridas_retorna_paginacao(self):
        self._assert_paginated('/api/corridas/')

    def test_certificados_qualidade_retorna_paginacao(self):
        self._assert_paginated('/api/certificados-qualidade/')

    def test_atendimentos_estoque_retorna_paginacao(self):
        self._assert_paginated('/api/atendimentos-estoque/')

    def test_estoque_saldos_retorna_paginacao(self):
        self._assert_paginated('/api/estoque/saldos/')

    def test_busca_fornecedor_por_razao_social(self):
        resp = self.client.get('/api/fornecedores/', {
            'search': 'Fornecedor 407',
            'page': 1,
        })
        self.assertEqual(resp.status_code, 200)
        nomes = [r.get('razao_social') or '' for r in resp.json()['results']]
        self.assertTrue(any('Fornecedor 407' in n for n in nomes))

    def test_filtro_status_proposta(self):
        resp = self.client.get('/api/propostas/', {'status': 'ABERTA', 'page': 1})
        self.assertEqual(resp.status_code, 200)
        for row in resp.json()['results']:
            self.assertIn('ABERTA', (row.get('status') or '').upper())

    def test_busca_regra_fiscal_ncm(self):
        resp = self.client.get('/api/regras-fiscais/', {'search': '73079300', 'page': 1})
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()['count'], 1)

    def test_autocomplete_fornecedor_sem_page(self):
        resp = self.client.get('/api/fornecedores/', {'limit': 5})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertLessEqual(len(data), 5)

    def test_listagem_nf_entrada_historica_nao_retorna_xml(self):
        resp = self.client.get('/api/nf-entradas-historicas-importadas/', {'page': 1, 'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        for row in resp.json()['results']:
            self.assertNotIn('xml', row)
            self.assertNotIn('xml_conteudo', row)

    def test_page_size_maximo_respeitado(self):
        resp = self.client.get('/api/fornecedores/', {'page': 1, 'page_size': 500})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['page_size'], 20)
