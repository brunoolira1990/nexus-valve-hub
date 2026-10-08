"""ERP 4.0.14.x — busca NF-e Saída pelo pedido do cliente (pedido_cliente_numero)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.core.document_numbering import filtrar_queryset_por_numeros_documento
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
from apps.fiscal.nfe_saida_listagem import montar_listagem_resumo_nfe


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _nf(*, numero: str, pedido_cliente: str, status: str = 'RASCUNHO') -> NFeSaida:
    emp = Empresa.objects.create(razao_social=f'E-{uuid.uuid4().hex[:4]}', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social=f'C-{uuid.uuid4().hex[:4]}', cnpj=_cnpj(), uf='RJ')
    return NFeSaida.objects.create(
        numero=numero,
        cliente=cli,
        empresa_emitente=emp,
        data=date.today(),
        valor_total=Decimal('100'),
        status=status,
        pedido_cliente_numero=pedido_cliente,
    )


class BuscaNFeSaidaPedidoClienteUnitTests(TestCase):
    """Campo real: NFeSaida.pedido_cliente_numero (sem migration / sem join)."""

    def test_campo_na_propria_nfe_sem_fuzzy(self):
        a = _nf(numero='RASC-A', pedido_cliente='4501949217')
        b = _nf(numero='RASC-B', pedido_cliente='4502949217')
        qs = NFeSaida.objects.filter(pk__in=[a.pk, b.pk])

        for termo in ('4501949217', '450194', '4501-949217', '4501 949217'):
            hit = list(filtrar_queryset_por_numeros_documento(qs, termo, 'pedido_cliente_numero'))
            self.assertEqual([n.pk for n in hit], [a.pk], msg=termo)

        # Finais comuns: 49217 e 949217 existem nos dois.
        for termo in ('49217', '949217'):
            ambos = list(filtrar_queryset_por_numeros_documento(qs, termo, 'pedido_cliente_numero'))
            self.assertEqual({n.pk for n in ambos}, {a.pk, b.pk}, msg=termo)

        self.assertEqual(
            [n.pk for n in filtrar_queryset_por_numeros_documento(qs, '4502-949217', 'pedido_cliente_numero')],
            [b.pk],
        )
        self.assertEqual(
            list(filtrar_queryset_por_numeros_documento(qs, '949217-4501', 'pedido_cliente_numero')),
            [],
        )
        self.assertEqual(
            list(filtrar_queryset_por_numeros_documento(qs, '999999', 'pedido_cliente_numero')),
            [],
        )

    def test_subtitulo_listagem_inclui_pedido_cliente(self):
        nf = _nf(numero='RASC-SUB', pedido_cliente='4501949217')
        ap = montar_apresentacao_nfe_saida(nf)
        self.assertIn('4501949217', ap.get('listagem_subtitulo') or '')
        resumo = montar_listagem_resumo_nfe(nf)
        self.assertIn('4501949217', resumo.get('subtitulo') or '')


class BuscaNFeSaidaPedidoClienteApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfecli', 'nfecli@test.com', 'x')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.nf_a = _nf(numero='NF-CLI-A', pedido_cliente='4501949217', status='RASCUNHO')
        self.nf_b = _nf(numero='NF-CLI-B', pedido_cliente='4502949217', status='RASCUNHO')
        self.nf_c = _nf(numero='NF-CLI-C', pedido_cliente='OC-ABC-99', status='CANCELADA')

    def _search(self, termo: str, **extra):
        return self.api.get('/api/nf-saidas/', {'search': termo, **extra})

    def test_busca_api_completo_trechos_e_tokens(self):
        for termo in ('4501949217', '450194', '4501-949217', '4501 949217'):
            r = self._search(termo)
            self.assertEqual(r.status_code, status.HTTP_200_OK, msg=termo)
            ids = [row['id'] for row in r.data['results']]
            self.assertIn(self.nf_a.id, ids, msg=termo)
            self.assertNotIn(self.nf_b.id, ids, msg=termo)

        # Últimos dígitos compartilhados → ambos.
        r_fin = self._search('49217')
        self.assertEqual({row['id'] for row in r_fin.data['results']}, {self.nf_a.id, self.nf_b.id})

        r_inv = self._search('949217-4501')
        self.assertEqual(r_inv.data['results'], [])

        r_miss = self._search('88887777')
        self.assertEqual(r_miss.data['results'], [])

    def test_duas_nfe_final_igual_distintas_por_prefixo(self):
        r = self._search('949217')
        ids = {row['id'] for row in r.data['results']}
        self.assertEqual(ids, {self.nf_a.id, self.nf_b.id})
        r_a = self._search('4501-949217')
        self.assertEqual([row['id'] for row in r_a.data['results']], [self.nf_a.id])
        r_b = self._search('4502-949217')
        self.assertEqual([row['id'] for row in r_b.data['results']], [self.nf_b.id])

    def test_filtro_status_e_paginacao(self):
        r = self._search('OC-ABC', status='CANCELADA')
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['id'], self.nf_c.id)

        r2 = self._search('4501949217', status='CANCELADA')
        self.assertEqual(r2.data['results'], [])

        r3 = self._search('4501', page_size=1, page=1)
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r3.data['results']), 1)
        self.assertIn('count', r3.data)

    def test_sem_duplicidade_e_subtitulo(self):
        r = self._search('4501949217')
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(len(ids), len(set(ids)))
        row = next(x for x in r.data['results'] if x['id'] == self.nf_a.id)
        sub = (row.get('listagem_resumo') or {}).get('subtitulo') or ''
        self.assertIn('4501949217', sub)

    def test_busca_por_numero_nfe_e_interno_preservada(self):
        r = self._search('NF-CLI-A')
        ids = [row['id'] for row in r.data['results']]
        self.assertIn(self.nf_a.id, ids)
