"""Filtro de listagem: NF-e autorizadas a prazo sem Contas a Receber."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.comercial.payment_terms import compute_due_dates
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.services.titulo import criar_titulo_financeiro
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_condicao_pagamento import (
    filtrar_queryset_deve_gerar_cobranca_a_prazo,
    nfe_deve_gerar_cobranca_a_prazo,
)
from apps.fiscal.nfe_saida_duplicatas import aplicar_duplicatas_nfe_saida
from apps.fiscal.nfe_saida_financeiro import filtrar_queryset_autorizadas_a_prazo_sem_contas_receber
from apps.fiscal.tests.test_nfe_saida_40143_gerar_contas_receber import _autorizar_nf, _autorizar_nf_homologacao
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf


def _marcar_plano(nf: NFeSaida, dias: list[int]) -> NFeSaida:
    nf.dias_parcelas = list(dias)
    nf.quantidade_parcelas = len(dias)
    nf.condicao_pagamento_texto = '/'.join(str(d) for d in dias) if dias else ''
    nf.titulos_receber = []
    nf.vencimentos_finais = []
    if dias and not (len(dias) == 1 and dias[0] == 0):
        base = nf.data or date.today()
        nf.vencimentos_finais = compute_due_dates(base, dias)
    nf.save(
        update_fields=[
            'dias_parcelas',
            'quantidade_parcelas',
            'condicao_pagamento_texto',
            'titulos_receber',
            'vencimentos_finais',
        ],
    )
    if dias and not (len(dias) == 1 and dias[0] == 0):
        aplicar_duplicatas_nfe_saida(nf)
    return nf


def _ids_filtro(client: APIClient) -> set[int]:
    res = client.get('/api/nf-saidas/', {'a_prazo_sem_contas_receber': 'true'})
    assert res.status_code == 200
    body = res.json()
    rows = body if isinstance(body, list) else body.get('results', [])
    return {int(r['id']) for r in rows}


class FiltroAPrazoSemContasReceberTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('filtrocr', 'filtrocr@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _nf_base(self) -> NFeSaida:
        _, _, nf = _pedido_nf()
        return _autorizar_nf(nf)

    def test_producao_a_prazo_sem_cr_aparece(self):
        nf = _marcar_plano(self._nf_base(), [30])
        self.assertTrue(nfe_deve_gerar_cobranca_a_prazo(nf))
        self.assertIn(nf.pk, _ids_filtro(self.client))

    def test_producao_a_prazo_com_cr_nao_aparece(self):
        nf = _marcar_plano(self._nf_base(), [30])
        criar_titulo_financeiro(
            tipo=TituloFinanceiro.Tipo.RECEBER,
            cliente_id=nf.cliente_id,
            data_emissao=nf.data or date.today(),
            data_vencimento=(nf.data or date.today()),
            valor_original=nf.valor_total,
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
            origem_id=nf.pk,
            origem_numero=str(nf.numero_nfe or nf.pk),
            usuario=self.user,
        )
        self.assertNotIn(nf.pk, _ids_filtro(self.client))

    def test_avista_nao_aparece(self):
        nf = _marcar_plano(self._nf_base(), [0])
        self.assertFalse(nfe_deve_gerar_cobranca_a_prazo(nf))
        self.assertNotIn(nf.pk, _ids_filtro(self.client))

    def test_misto_sem_cr_aparece(self):
        nf = _marcar_plano(self._nf_base(), [0, 30])
        self.assertTrue(nfe_deve_gerar_cobranca_a_prazo(nf))
        self.assertIn(nf.pk, _ids_filtro(self.client))

    def test_condicao_ausente_segue_fallback_elegivel(self):
        nf = _marcar_plano(self._nf_base(), [])
        self.assertTrue(nfe_deve_gerar_cobranca_a_prazo(nf))
        qs = filtrar_queryset_deve_gerar_cobranca_a_prazo(NFeSaida.objects.filter(pk=nf.pk))
        self.assertTrue(qs.filter(pk=nf.pk).exists())
        self.assertIn(nf.pk, _ids_filtro(self.client))

    def test_homologacao_nao_aparece(self):
        _, _, nf = _pedido_nf()
        nf = _autorizar_nf_homologacao(nf)
        _marcar_plano(nf, [30])
        self.assertNotIn(nf.pk, _ids_filtro(self.client))

    def test_cancelada_nao_aparece(self):
        nf = _marcar_plano(self._nf_base(), [30])
        nf.status = 'CANCELADA_PRODUCAO'
        nf.status_emissao_sefaz = 'CANCELADA_PRODUCAO'
        nf.save(update_fields=['status', 'status_emissao_sefaz'])
        self.assertNotIn(nf.pk, _ids_filtro(self.client))

    def test_nao_autorizada_nao_aparece(self):
        _, _, nf = _pedido_nf()
        _marcar_plano(nf, [30])
        self.assertNotIn(nf.pk, _ids_filtro(self.client))

    def test_sem_parametro_listagem_inclui_todas(self):
        nf_prazo = _marcar_plano(self._nf_base(), [30])
        # Segunda NF no mesmo emitente/cliente (evita CNPJ duplicado do helper).
        nf_vista = NFeSaida.objects.create(
            numero=f'RASCUNHO-VISTA-{nf_prazo.pk}',
            cliente_id=nf_prazo.cliente_id,
            data=nf_prazo.data,
            status=nf_prazo.status,
            valor_total=nf_prazo.valor_total,
            ambiente_emissao=nf_prazo.ambiente_emissao,
            status_emissao_sefaz=nf_prazo.status_emissao_sefaz,
            serie_nfe=nf_prazo.serie_nfe,
            numero_nfe='000000099',
            cstat_autorizacao=nf_prazo.cstat_autorizacao,
            protocolo_autorizacao=nf_prazo.protocolo_autorizacao or '1',
            chave_acesso=(nf_prazo.chave_acesso or '0')[:-1] + '9',
            xml_autorizado=nf_prazo.xml_autorizado or '<nfe/>',
            dias_parcelas=[0],
            quantidade_parcelas=1,
            condicao_pagamento_texto='0',
        )
        res = self.client.get('/api/nf-saidas/')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        rows = body if isinstance(body, list) else body.get('results', [])
        ids = {int(r['id']) for r in rows}
        self.assertIn(nf_prazo.pk, ids)
        self.assertIn(nf_vista.pk, ids)
        # Com filtro, à vista continua fora.
        self.assertNotIn(nf_vista.pk, _ids_filtro(self.client))
        self.assertIn(nf_prazo.pk, _ids_filtro(self.client))

    def test_parametro_invalido_nao_aplica_filtro(self):
        nf = _marcar_plano(self._nf_base(), [0])
        res = self.client.get('/api/nf-saidas/', {'a_prazo_sem_contas_receber': 'foo'})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        rows = body if isinstance(body, list) else body.get('results', [])
        ids = {int(r['id']) for r in rows}
        self.assertIn(nf.pk, ids)

    def test_queryset_helper_nao_n_plus_one(self):
        nf = _marcar_plano(self._nf_base(), [30])
        with self.assertNumQueries(1):
            list(filtrar_queryset_autorizadas_a_prazo_sem_contas_receber(NFeSaida.objects.all()))
        self.assertTrue(
            filtrar_queryset_autorizadas_a_prazo_sem_contas_receber(
                NFeSaida.objects.filter(pk=nf.pk),
            ).exists(),
        )
