"""Fase 1 PR 3 — eventos de auditoria gravados pelas actions reais de entrada.

Cobertura mínima por categoria (conferência, estoque, financeiro, devolução, CT-e)
+ tolerância (falha de auditoria jamais derruba a operação) + diff real via
`estado_anterior` + snapshot fallback (`_snapshot`) quando não há diff.

As actions cujo serviço é pesado/ambiental (reabrir, aplicar estoque físico,
rateio, gerar contas a pagar) são exercitadas com o serviço de domínio mockado
no namespace em que a view o consome — o que se testa aqui é o PLUG da view
(entidade correta, `acao` correta, `estado_anterior` correto), não o serviço.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.auditoria.models import RegistroAuditoria
from apps.cadastros.models import Empresa
from apps.fiscal.models import CTeHistoricoImportado, NFeEntradaConferencia
from apps.fiscal.tests.test_conferencia_preparar_estoque import (
    _criar_regra_fiscal_entrada_minima,
    _setup_conferencia,
)


def _evento(acao: str, model_name: str, object_id: int) -> RegistroAuditoria:
    return (
        RegistroAuditoria.objects.filter(
            app_label='fiscal',
            model_name=model_name,
            object_id=object_id,
            acao=acao,
        )
        .order_by('-id')
        .first()
    )


class NFeEntradaActionsAuditoriaTests(TestCase):
    """Actions do NFeEntradaHistoricaImportadaViewSet — entidade auditada: NFeEntradaConferencia."""

    def setUp(self):
        _criar_regra_fiscal_entrada_minima()

    def test_post_conferencia_grava_evento_conferir_contra_conferencia(self):
        ctx = _setup_conferencia('pr3a')
        resp = ctx['client'].post(ctx['url_conf'], {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        evento = _evento('conferir', 'nfeentradaconferencia', ctx['conf'].id)
        self.assertIsNotNone(evento, "evento 'conferir' não gravado")
        ator = get_user_model().objects.get(username='prep_pr3a')
        self.assertEqual(evento.ator_id, ator.id)
        self.assertNotIn('_snapshot', evento.alteracoes)  # veio estado_anterior explícito

    def test_reabrir_grava_evento_reabrir(self):
        ctx = _setup_conferencia('pr3b')
        url = reverse('nf-entrada-hist-importada-reabrir-conferencia', args=[ctx['nf'].id])
        with mock.patch(
            'apps.fiscal.views.reabrir_entrada_fornecedor',
            return_value={'conferencia': ctx['conf'], 'alocacoes_removidas': 0},
        ):
            resp = ctx['client'].post(url, {'motivo': 'teste PR 3'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        evento = _evento('reabrir', 'nfeentradaconferencia', ctx['conf'].id)
        self.assertIsNotNone(evento, "evento 'reabrir' não gravado")

    def test_preparar_estoque_grava_evento_com_diff_real_de_status(self):
        ctx = _setup_conferencia('pr3c', com_pedido=False)
        r_save = ctx['client'].post(
            ctx['url_conf'],
            {
                'pedido_compra_id': None,
                'itens': [
                    {'id': ctx['linha1'].id, 'produto_id': ctx['prod'].id, 'status': 'PRODUTO_VINCULADO'},
                    {'id': ctx['linha2'].id, 'status': 'IGNORADO', 'motivo_ignorado': 'Não usado'},
                ],
            },
            format='json',
        )
        self.assertEqual(r_save.status_code, status.HTTP_200_OK, r_save.content)

        r_prep = ctx['client'].post(ctx['url_prep'], {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_200_OK, r_prep.content)

        evento = _evento('preparar_estoque', 'nfeentradaconferencia', ctx['conf'].id)
        self.assertIsNotNone(evento, "evento 'preparar_estoque' não gravado")
        # estado_anterior congelado ANTES do save -> diff real antes/depois.
        self.assertEqual(
            evento.alteracoes.get('status'),
            {
                'antes': NFeEntradaConferencia.Status.PENDENTE,
                'depois': NFeEntradaConferencia.Status.PREPARADA,
            },
        )

    def test_aplicar_estoque_grava_evento_aplicar_estoque(self):
        ctx = _setup_conferencia('pr3d')
        url = reverse('nf-entrada-hist-importada-aplicar-estoque-conferencia', args=[ctx['nf'].id])
        with mock.patch(
            'apps.fiscal.views.aplicar_estoque_fisico_conferencia',
            return_value={'itens_aplicados': 0},
        ):
            resp = ctx['client'].post(url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        evento = _evento('aplicar_estoque', 'nfeentradaconferencia', ctx['conf'].id)
        self.assertIsNotNone(evento, "evento 'aplicar_estoque' não gravado")

    def test_gerar_saida_devolucao_compra_grava_evento_com_snapshot(self):
        ctx = _setup_conferencia('pr3e')
        url = reverse('nf-entrada-hist-importada-gerar-saida-devolucao-compra', args=[ctx['nf'].id])
        with mock.patch(
            'apps.fiscal.nfe_saida_from_entrada_devolucao.gerar_saida_devolucao_compra',
            return_value={'ok': True, 'saida_id': 1},
        ):
            resp = ctx['client'].post(url, {'motivo': 'DEFEITO'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        evento = _evento('gerar_saida_devolucao_compra', 'nfeentradaconferencia', ctx['conf'].id)
        self.assertIsNotNone(evento, "evento 'gerar_saida_devolucao_compra' não gravado")
        # Sem estado_anterior (a conferência não é mutada) -> snapshot fallback.
        self.assertIn('_snapshot', evento.alteracoes)
        self.assertIn('status', evento.alteracoes['_snapshot'])


class CTeHistoricoActionsAuditoriaTests(TestCase):
    """Actions do CTeHistoricoImportadoViewSet — entidade auditada: CTeHistoricoImportado."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='pr3_cte', password='x')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.empresa = Empresa.objects.create(
            razao_social='Nexus Tomadora PR 3',
            cnpj='11.111.111/0001-11',
        )

    def _cte(self, *, sufixo: str) -> CTeHistoricoImportado:
        return CTeHistoricoImportado.objects.create(
            chave_acesso=('35' + sufixo).ljust(44, '0')[:44],
            numero=f'CTE{sufixo}'[:16],
            serie='1',
            modelo='67',
            dh_emissao=timezone.make_aware(datetime(2026, 10, 1, 10, 0, 0)),
            cstat='100',
            valor_total_servico=Decimal('1500.00'),
            empresa_tomadora=self.empresa,
            status_conferencia=CTeHistoricoImportado.StatusConferencia.IMPORTADO,
        )

    def _simular_conferir(self, cte, usuario, dados=None):
        cte.status_conferencia = CTeHistoricoImportado.StatusConferencia.CONFERIDO
        cte.apto_operacional = True
        cte.conferido_por = usuario
        cte.conferido_em = timezone.now()
        cte.save(
            update_fields=['status_conferencia', 'apto_operacional', 'conferido_por', 'conferido_em'],
        )
        return cte

    def test_cte_conferir_grava_evento_contra_ctehistoricoimportado(self):
        cte = self._cte(sufixo='01')
        url = reverse('cte-hist-importado-conferir', args=[cte.id])
        with mock.patch(
            'apps.fiscal.cte_historico_conferencia.conferir_cte_importado',
            side_effect=self._simular_conferir,
        ):
            resp = self.api.post(url, {'confirmar_tomador': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        evento = _evento('conferir', 'ctehistoricoimportado', cte.id)
        self.assertIsNotNone(evento, "evento 'conferir' do CT-e não gravado")
        self.assertEqual(evento.ator_id, self.user.id)
        self.assertEqual(
            evento.alteracoes.get('status_conferencia'),
            {'antes': 'IMPORTADO', 'depois': 'CONFERIDO'},
        )

    def test_cte_marcar_divergente_grava_evento(self):
        cte = self._cte(sufixo='02')
        url = reverse('cte-hist-importado-marcar-divergente', args=[cte.id])
        resp = self.api.post(url, {'motivo': 'Valor divergente do XML'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        evento = _evento('marcar_divergente', 'ctehistoricoimportado', cte.id)
        self.assertIsNotNone(evento, "evento 'marcar_divergente' não gravado")

    def test_cte_gerar_contas_pagar_grava_evento_com_snapshot(self):
        cte = self._cte(sufixo='03')
        url = reverse('cte-hist-importado-gerar-contas-pagar-cte', args=[cte.id])
        with mock.patch(
            'apps.fiscal.cte_financeiro.gerar_contas_pagar_de_cte',
            return_value={'ok': True, 'titulos': []},
        ):
            resp = self.api.post(url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        evento = _evento('gerar_contas_pagar', 'ctehistoricoimportado', cte.id)
        self.assertIsNotNone(evento, "evento 'gerar_contas_pagar' do CT-e não gravado")
        self.assertIn('_snapshot', evento.alteracoes)
        self.assertIn('status_conferencia', evento.alteracoes['_snapshot'])

    def test_cte_salvar_rateio_grava_evento(self):
        cte = self._cte(sufixo='04')
        url = reverse('cte-hist-importado-salvar-rateio-frete', args=[cte.id])

        def _simular_rateio(cte_obj, *, linhas, metodo, usuario):
            cte_obj.rateado_em = timezone.now()
            cte_obj.rateado_por = usuario
            cte_obj.save(update_fields=['rateado_em', 'rateado_por'])
            return cte_obj

        with (
            mock.patch(
                'apps.fiscal.cte_financeiro.salvar_rateio_frete_cte',
                side_effect=_simular_rateio,
            ),
            mock.patch(
                'apps.fiscal.cte_financeiro.sugerir_rateio_frete_cte',
                return_value={'linhas': []},
            ),
        ):
            resp = self.api.post(url, {'linhas': [], 'metodo': 'MANUAL'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        evento = _evento('salvar_rateio', 'ctehistoricoimportado', cte.id)
        self.assertIsNotNone(evento, "evento 'salvar_rateio' não gravado")


class AuditoriaToleranciaTests(TestCase):
    """Falha de auditoria NUNCA derruba a operação fiscal (guarda do PR 1)."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='pr3_tol', password='x')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.empresa = Empresa.objects.create(
            razao_social='Nexus Tomadora PR 3 Tol',
            cnpj='12.121.212/0012-12',
        )

    def test_falha_em_registrar_auditoria_mantem_acao_2xx(self):
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso='3599'.ljust(44, '0'),
            numero='CTETOL',
            serie='1',
            dh_emissao=timezone.make_aware(datetime(2026, 10, 1, 10, 0, 0)),
            empresa_tomadora=self.empresa,
        )
        url = reverse('cte-hist-importado-marcar-divergente', args=[cte.id])
        with mock.patch(
            'apps.fiscal.auditoria_entrada.registrar_auditoria',
            side_effect=RuntimeError('auditoria quebrada de propósito'),
        ):
            resp = self.api.post(url, {'motivo': 'Operação deve sobreviver'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        cte.refresh_from_db()
        self.assertEqual(cte.status_conferencia, CTeHistoricoImportado.StatusConferencia.DIVERGENTE)
        self.assertIsNone(_evento('marcar_divergente', 'ctehistoricoimportado', cte.id))
