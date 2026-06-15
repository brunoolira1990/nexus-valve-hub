"""Checklist produção — status conferência e DANFE BFR."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.validacao_producao import montar_validacao_emissao_producao
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.tests.nfe_4015_test_support import NFe4015GruposMixin, vincular_grupo_teste
from apps.fiscal.tests.test_nfe_saida_producao_4015 import (
    _pedido_nf,
    _preparar_nf_indicadores,
    _preparar_pronta,
)


class NFeProducaoStatusDanfeChecklistTests(NFe4015GruposMixin, TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.admin_user = User.objects.create_user('admst', 'admst@test.com', 'x')
        vincular_grupo_teste(self.admin_user, 'admin')
        self.pedido, self.nf = _pedido_nf()
        self.nf = _preparar_nf_indicadores(self.nf)
        self.nf = _preparar_pronta(self.nf, self.admin_user)

    @override_settings(NFE_PRODUCAO_HABILITADA=True, DANFE_BLOCK_EMISSION_IF_BFR_FAILS=True)
    @patch('apps.fiscal.danfe_render.validar_danfe_bfr_para_emissao')
    def test_checklist_nao_acusa_status_quando_pronta(self, mock_bfr):
        mock_bfr.return_value = None
        payload = montar_validacao_emissao_producao(self.nf)
        codigos = [p['codigo'] for p in payload['pendencias']]
        self.assertNotIn('conferencia_nao_pronta', codigos)
        self.assertEqual(self.nf.status_conferencia, NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO)

    @override_settings(NFE_PRODUCAO_HABILITADA=True, DANFE_BLOCK_EMISSION_IF_BFR_FAILS=True)
    @patch('apps.fiscal.danfe_render.validar_danfe_bfr_para_emissao')
    def test_checklist_nao_adiciona_alerta_bfr_generico_quando_ok(self, mock_bfr):
        mock_bfr.return_value = None
        payload = montar_validacao_emissao_producao(self.nf)
        msgs = [p['mensagem'] for p in payload['pendencias']]
        self.assertFalse(any('falha no renderer bloqueia emissão' in m.lower() for m in msgs))
        mock_bfr.assert_called_once()

    @override_settings(NFE_PRODUCAO_HABILITADA=True, DANFE_BLOCK_EMISSION_IF_BFR_FAILS=True)
    @patch('apps.fiscal.danfe_render.validar_danfe_bfr_para_emissao')
    def test_checklist_bfr_falha_motivo_claro(self, mock_bfr):
        from apps.fiscal.danfe_render import DanfeBfrRenderError

        mock_bfr.side_effect = DanfeBfrRenderError(
            'Não foi possível gerar o DANFE pelo renderizador oficial BFR.',
            nfe_saida_id=self.nf.pk,
            erro_tipo='DanfeBfrError',
            trace_id='trace-test-123',
        )
        payload = montar_validacao_emissao_producao(self.nf)
        bfr = [p for p in payload['pendencias'] if p['codigo'] == 'danfe_bfr_obrigatorio']
        self.assertEqual(len(bfr), 1)
        self.assertIn('BFR', bfr[0]['mensagem'])
        self.assertIn('trace-test-123', bfr[0]['mensagem'])

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.danfe_render.validar_danfe_bfr_para_emissao', return_value=None)
    def test_conferencia_emissao_producao_expoe_status_conferencia(self, _mock_bfr):
        conf = montar_conferencia_nfe_saida(self.nf, modo='completo', usuario=self.admin_user)
        self.assertEqual(
            conf['emissao_producao']['status_conferencia'],
            NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO,
        )
        self.assertEqual(conf['emissao_sefaz']['status_conferencia'], NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO)
