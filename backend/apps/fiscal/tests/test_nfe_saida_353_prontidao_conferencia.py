"""NF-e Saída 3.5.3 — fluxo de prontidão da conferência."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.models import AtendimentoEstoque, ItemNFeSaida, NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_prontidao import (
    MSG_MARCAR_PRONTA_PENDENCIAS,
    marcar_nfe_pronta_para_emissao,
    validar_conferencia_nfe,
)
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _regra_84818200_sp_rj() -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm='84818200',
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'Venda SP - contribuinte',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
            'reforma_tributaria': {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_cbs': '0.9',
            },
        },
    )
    return regra


@override_settings(
    USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True,
    DANFE_BLOCK_EMISSION_IF_BFR_FAILS=False,
)
class NFeSaida353ProntidaoConferenciaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe353', 'nfe353@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        _regra_84818200_sp_rj()

    def _nf_rascunho(self) -> NFeSaida:
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['indicadores_fiscais_confirmados'])
        return NFeSaida.objects.prefetch_related('itens__produto').get(pk=nf.pk)

    def test_nova_nf_inicia_em_conferencia(self):
        nf = self._nf_rascunho()
        self.assertEqual(nf.status_conferencia, NFeSaida.StatusConferencia.EM_CONFERENCIA)

    def test_get_conferencia_inclui_prontidao(self):
        nf = self._nf_rascunho()
        conf = self.client.get(f'/api/nf-saidas/{nf.pk}/conferencia/').json()
        self.assertIn('prontidao', conf)
        self.assertIn('status_conferencia', conf['prontidao'])
        self.assertIn('pode_validar_conferencia', conf['permissoes'])

    def test_lista_inclui_status_conferencia(self):
        nf = self._nf_rascunho()
        lista = self.client.get('/api/nf-saidas/').json()
        rows = lista if isinstance(lista, list) else lista.get('results', [])
        row = next(x for x in rows if x['id'] == nf.pk)
        self.assertIn('listagem_resumo', row)
        det = self.client.get(f'/api/nf-saidas/{nf.pk}/').json()
        self.assertEqual(det['status_conferencia'], 'EM_CONFERENCIA')
        self.assertTrue(det.get('status_conferencia_display'))

    def test_validar_com_pendencias_marca_com_pendencias(self):
        nf = self._nf_rascunho()
        for it in nf.itens.all():
            it.snapshot_fiscal = {}
            it.save(update_fields=['snapshot_fiscal'])
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/validar-conferencia/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        nf.refresh_from_db()
        self.assertEqual(nf.status_conferencia, NFeSaida.StatusConferencia.COM_PENDENCIAS)
        self.assertTrue(
            NFeSaidaEvento.objects.filter(
                nfe_saida=nf,
                tipo_evento=NFeSaidaEvento.TipoEvento.CONFERENCIA_COM_PENDENCIAS,
            ).exists(),
        )

    def test_validar_sem_pendencias_marca_conferida(self):
        nf = self._nf_rascunho()
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/validar-conferencia/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        nf.refresh_from_db()
        self.assertEqual(nf.status_conferencia, NFeSaida.StatusConferencia.CONFERIDA)
        self.assertTrue(res.json()['prontidao']['pode_marcar_pronta'])

    def test_marcar_pronta_sem_pendencias(self):
        nf = self._nf_rascunho()
        validar_conferencia_nfe(nf, usuario=self.user)
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/marcar-pronta/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        nf.refresh_from_db()
        self.assertEqual(nf.status_conferencia, NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO)
        self.assertIsNotNone(nf.conferencia_marcada_pronta_em)
        evt = NFeSaidaEvento.objects.get(
            nfe_saida=nf,
            tipo_evento=NFeSaidaEvento.TipoEvento.PRONTA_PARA_EMISSAO,
        )
        self.assertEqual(evt.resumo.get('status_conferencia_novo'), 'PRONTA_PARA_EMISSAO')

    def test_marcar_pronta_sincroniza_cenario_fiscal_vigente(self):
        nf = self._nf_rascunho()
        item = nf.itens.first()
        self.assertNotIn('regra_fiscal_saida_id', item.snapshot_fiscal)

        res = self.client.post(f'/api/nf-saidas/{nf.pk}/marcar-pronta/')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data['sincronizacao_cenario']['aplicado'])
        self.assertGreaterEqual(data['sincronizacao_cenario']['itens_atualizados'], 1)
        item.refresh_from_db()
        self.assertEqual(item.snapshot_fiscal['cfop'], '5102')
        self.assertTrue(item.snapshot_fiscal.get('regra_fiscal_saida_id'))
        self.assertTrue(item.snapshot_fiscal.get('cenario_fiscal_saida_id'))
        nf.refresh_from_db()
        self.assertEqual(nf.status_conferencia, NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO)
        self.assertTrue(
            NFeSaidaEvento.objects.filter(
                nfe_saida=nf,
                tipo_evento=NFeSaidaEvento.TipoEvento.IMPOSTOS_ATUALIZADOS,
            ).exists(),
        )

    def test_marcar_pronta_com_pendencias_retorna_400(self):
        nf = self._nf_rascunho()
        nf.itens.update(snapshot_fiscal={})
        # Sem regra vigente, a sincronização automática não pode reparar o item.
        RegraFiscalSaida.objects.all().delete()
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/marcar-pronta/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sem regra aplicável', res.json()['mensagem'])

    def test_marcar_pronta_autorizada_interna_bloqueia(self):
        nf = self._nf_rascunho()
        nf.status = 'AUTORIZADA_INTERNA'
        nf.save(update_fields=['status'])
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/marcar-pronta/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_marcar_pronta_cancelada_interna_bloqueia(self):
        nf = self._nf_rascunho()
        nf.status = 'CANCELADA_INTERNA'
        nf.save(update_fields=['status'])
        res = self.client.post(f'/api/nf-saidas/{nf.pk}/marcar-pronta/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_salvar_conferencia_apos_pronta_invalida(self):
        nf = self._nf_rascunho()
        validar_conferencia_nfe(nf, usuario=self.user)
        marcar_nfe_pronta_para_emissao(nf, usuario=self.user)
        res = self.client.patch(
            f'/api/nf-saidas/{nf.pk}/',
            {'observacoes_nfe': 'Obs alterada pós-pronta'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        nf.refresh_from_db()
        self.assertNotEqual(nf.status_conferencia, NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO)
        self.assertTrue(
            NFeSaidaEvento.objects.filter(
                nfe_saida=nf,
                tipo_evento=NFeSaidaEvento.TipoEvento.PRONTIDAO_INVALIDADA,
            ).exists(),
        )

    def test_atualizar_fiscal_apos_pronta_invalida(self):
        nf = self._nf_rascunho()
        validar_conferencia_nfe(nf, usuario=self.user)
        marcar_nfe_pronta_para_emissao(nf, usuario=self.user)
        with patch(
            'apps.fiscal.nfe_saida_atualizar_impostos.preparar_atualizacao_impostos_nfe',
        ) as mock_prev:
            mock_prev.return_value = {
                'pode_aplicar': True,
                'resumo': {'itens_com_regra': 1, 'itens_sem_regra': 0, 'recomendacoes_sugeridas': 0},
                'itens': [
                    {
                        'item_id': nf.itens.first().pk,
                        'regra_encontrada': True,
                        'alteracoes': [{'campo': 'icms', 'antes': '', 'depois': 'x'}],
                        '_snapshot_novo': {'ncm': '84818200', 'cfop': '5102'},
                    },
                ],
                'textos_fiscais': {},
            }
            res = self.client.post(f'/api/nf-saidas/{nf.pk}/atualizar-impostos/aplicar/', {})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        nf.refresh_from_db()
        self.assertEqual(nf.status_conferencia, NFeSaida.StatusConferencia.EM_CONFERENCIA)

    def test_marcar_pronta_nao_movimenta_estoque_nem_financeiro(self):
        nf = self._nf_rascunho()
        validar_conferencia_nfe(nf, usuario=self.user)
        qtd_atend = AtendimentoEstoque.objects.filter(item_nf_saida__nf=nf).count()
        titulos_antes = list(nf.titulos_receber or [])
        marcar_nfe_pronta_para_emissao(nf, usuario=self.user)
        nf.refresh_from_db()
        self.assertEqual(AtendimentoEstoque.objects.filter(item_nf_saida__nf=nf).count(), qtd_atend)
        self.assertEqual(list(nf.titulos_receber or []), titulos_antes)
        self.assertEqual(nf.status, 'RASCUNHO')

    def test_get_prontidao_endpoint(self):
        nf = self._nf_rascunho()
        data = self.client.get(f'/api/nf-saidas/{nf.pk}/prontidao/').json()
        self.assertEqual(data['nfe_saida_id'], nf.pk)
        self.assertEqual(data['status'], 'RASCUNHO')

    def test_conferencia_payload_permite_marcar_apos_validar(self):
        nf = self._nf_rascunho()
        validar_conferencia_nfe(nf, usuario=self.user)
        conf = montar_conferencia_nfe_saida(nf, modo='completo', incluir_checklist=True)
        self.assertTrue(conf['permissoes']['pode_marcar_pronta'])
        self.assertEqual(conf['prontidao']['status_conferencia'], 'CONFERIDA')
