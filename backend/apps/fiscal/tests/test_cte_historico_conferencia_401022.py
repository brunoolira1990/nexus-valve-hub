"""ERP 4.0.10.2.2 — conferência segura de CT-e importado."""

from __future__ import annotations

import copy
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.cte_historico_conferencia import (
    ConferenciaCteErro,
    conferir_cte_importado,
    marcar_cte_importado_divergente,
    ignorar_cte_importado_operacionalmente,
    queryset_cte_entrada_operacional,
)
from apps.fiscal.dfe_classificacao import pode_entrar_apuracao
from apps.fiscal.models import CTeEntrada, CTeHistoricoImportado, NFeEntradaHistoricaImportada
from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal


def _dh() -> datetime:
    return timezone.make_aware(datetime(2026, 5, 15, 10, 0, 0))


def _payload_conferir() -> dict:
    return {
        'observacao': 'Conferido em teste',
        'confirmar_tomador': True,
        'confirmar_transportadora': True,
        'confirmar_valores': True,
        'confirmar_documentos_referenciados': True,
    }


class CTeHistoricoConferencia401022Test(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='cte401022', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.dh = _dh()

    def _criar_cte(
        self,
        *,
        chave_suffix: str = '1',
        tp_amb: str = '1',
        cstat: str = '100',
        status_conferencia: str = CTeHistoricoImportado.StatusConferencia.PROCESSADO,
        cancelado: bool = False,
        valor: str = '1500.00',
    ) -> CTeHistoricoImportado:
        return CTeHistoricoImportado.objects.create(
            chave_acesso=chave_suffix * 44,
            numero=chave_suffix,
            serie='1',
            dh_emissao=self.dh,
            tp_amb=tp_amb,
            cstat=cstat,
            cancelado=cancelado,
            valor_total_servico=Decimal(valor),
            status_conferencia=status_conferencia,
            apto_operacional=False,
        )

    def test_conferir_producao_autorizado(self) -> None:
        cte = self._criar_cte()
        conferir_cte_importado(cte, self.user, _payload_conferir())
        cte.refresh_from_db()
        self.assertEqual(cte.status_conferencia, CTeHistoricoImportado.StatusConferencia.CONFERIDO)
        self.assertTrue(cte.apto_operacional)
        self.assertIsNotNone(cte.conferido_em)
        self.assertEqual(cte.conferido_por_id, self.user.id)

    def test_homologacao_nao_conferido_operacional(self) -> None:
        cte = self._criar_cte(chave_suffix='2', tp_amb='2')
        url = reverse('cte-hist-importado-conferir', args=[cte.id])
        resp = self.client.post(url, _payload_conferir(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        cte.refresh_from_db()
        self.assertFalse(cte.apto_operacional)

    def test_conferir_nao_cria_cte_entrada_legado(self) -> None:
        antes = CTeEntrada.objects.count()
        cte = self._criar_cte(chave_suffix='3')
        conferir_cte_importado(cte, self.user, _payload_conferir())
        self.assertEqual(CTeEntrada.objects.count(), antes)

    def test_conferir_registra_usuario_e_data(self) -> None:
        cte = self._criar_cte(chave_suffix='4')
        conferir_cte_importado(cte, self.user, {**_payload_conferir(), 'observacao': 'OK'})
        cte.refresh_from_db()
        self.assertEqual(cte.conferido_por_id, self.user.id)
        self.assertEqual(cte.observacao_conferencia, 'OK')

    def test_conferir_nao_altera_apuracao(self) -> None:
        cte = self._criar_cte(chave_suffix='5', valor='2000.00')
        params = {
            'empresa_id': None,
            'data_inicio': self.dh.date().isoformat(),
            'data_fim': self.dh.date().isoformat(),
            'fonte': 'HISTORICOS',
        }
        antes = build_apuracao_fiscal(copy.deepcopy(params))
        conferir_cte_importado(cte, self.user, _payload_conferir())
        depois = build_apuracao_fiscal(copy.deepcopy(params))
        self.assertEqual(
            antes.get('totais_consolidados', {}).get('cte', {}),
            depois.get('totais_consolidados', {}).get('cte', {}),
        )

    def test_divergente_exige_motivo(self) -> None:
        cte = self._criar_cte(chave_suffix='6')
        url = reverse('cte-hist-importado-marcar-divergente', args=[cte.id])
        resp = self.client.post(url, {'motivo': ''}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_divergente_nao_aparece_cte_entrada(self) -> None:
        cte = self._criar_cte(chave_suffix='7')
        marcar_cte_importado_divergente(cte, self.user, motivo='Valor divergente')
        self.assertEqual(queryset_cte_entrada_operacional().filter(pk=cte.pk).count(), 0)

    def test_conferido_aparece_cte_entrada(self) -> None:
        cte = self._criar_cte(chave_suffix='8')
        conferir_cte_importado(cte, self.user, _payload_conferir())
        self.assertEqual(queryset_cte_entrada_operacional().filter(pk=cte.pk).count(), 1)
        url = reverse('cteentrada-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ids = [r['id'] for r in results]
        self.assertIn(cte.id, ids)

    def test_ignorado_nao_aparece_cte_entrada(self) -> None:
        cte = self._criar_cte(chave_suffix='9')
        ignorar_cte_importado_operacionalmente(cte, self.user, motivo='Não usar operacionalmente')
        self.assertEqual(queryset_cte_entrada_operacional().filter(pk=cte.pk).count(), 0)

    def test_cancelado_nao_operacional(self) -> None:
        cte = self._criar_cte(
            chave_suffix='z',
            cancelado=True,
            status_conferencia=CTeHistoricoImportado.StatusConferencia.CANCELADO,
        )
        with self.assertRaises(ConferenciaCteErro):
            conferir_cte_importado(cte, self.user, _payload_conferir())
        cte.refresh_from_db()
        self.assertFalse(cte.apto_operacional)

    def test_lista_base_retorna_status_conferencia(self) -> None:
        self._criar_cte()
        url = reverse('cte-hist-importado-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data['results'][0]
        self.assertIn('status_conferencia', row)
        self.assertIn('apto_operacional', row)
        self.assertNotIn('xml', row)

    def test_lista_cte_entrada_apenas_aptos(self) -> None:
        ok = self._criar_cte(chave_suffix='a')
        diverg = self._criar_cte(chave_suffix='b')
        conferir_cte_importado(ok, self.user, _payload_conferir())
        marcar_cte_importado_divergente(diverg, self.user, motivo='Erro')
        url = reverse('cteentrada-list')
        resp = self.client.get(url)
        results = resp.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], ok.id)
        self.assertIn('sem_financeiro_automatico', results[0]['classificacao_dfe']['badges'])

    def test_documentos_vinculados_resumo(self) -> None:
        ch_nfe = '3' * 44
        NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=ch_nfe,
            numero='10',
            serie='1',
            dh_emissao=self.dh,
            tp_amb='1',
            cstat='100',
        )
        cte = self._criar_cte(chave_suffix='c')
        cte.chaves_nfe_vinculadas = [ch_nfe]
        cte.save(update_fields=['chaves_nfe_vinculadas'])
        url = reverse('cte-hist-importado-detail', args=[cte.id])
        resp = self.client.get(url)
        docs = resp.data.get('documentos_vinculados_resumo') or []
        self.assertTrue(any(d['localizada'] for d in docs))

    def test_homologacao_fora_apuracao(self) -> None:
        cte = self._criar_cte(chave_suffix='d', tp_amb='2')
        self.assertFalse(pode_entrar_apuracao(cte))

    def test_producao_continua_apuracao_apos_conferir(self) -> None:
        cte = self._criar_cte(chave_suffix='e')
        self.assertTrue(pode_entrar_apuracao(cte))
        conferir_cte_importado(cte, self.user, _payload_conferir())
        cte.refresh_from_db()
        self.assertTrue(pode_entrar_apuracao(cte))

    def test_endpoint_conferir_retorna_classificacao(self) -> None:
        cte = self._criar_cte(chave_suffix='f')
        url = reverse('cte-hist-importado-conferir', args=[cte.id])
        resp = self.client.post(url, _payload_conferir(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status_conferencia'], 'CONFERIDO')
        self.assertIn('classificacao_dfe', resp.data)

    def test_checklist_incompleto_rejeitado(self) -> None:
        cte = self._criar_cte(chave_suffix='g')
        url = reverse('cte-hist-importado-conferir', args=[cte.id])
        resp = self.client.post(url, {'confirmar_tomador': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
