"""ERP 4.0.13.6.12 — Performance e UX da conferência NF-e."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.nfe_xml_preliminar import (
    gerar_xml_nfe_preliminar,
    invalidar_xml_preliminar_armazenado,
)
from apps.fiscal.nfe_perf import nfe_perf_habilitado
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_prontidao import validar_conferencia_nfe
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa, _regra_sp_pa
from apps.fiscal.validacao_nfe_saida import MODO_VALIDACAO_COMPLETO, MODO_VALIDACAO_LEVE, validar_nfe_saida_para_emissao


class NFePerf4013612Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3612', 'nfe3612@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        regra = _regra_sp_pa()
        regra.reforma_tributaria = {
            'cst_ibs_cbs': '000',
            'classificacao_tributaria': '000001',
            'aliquota_ibs_estadual': '0,1',
            'aliquota_cbs': '0,9',
        }
        regra.save(update_fields=['reforma_tributaria'])

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def _nf_pronta(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        if nf.empresa_emitente_id and not (nf.empresa_emitente.ie or '').strip():
            emp = nf.empresa_emitente
            emp.ie = '123456789012'
            emp.save(update_fields=['ie'])
        from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe

        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        return nf

    @override_settings(DEBUG=True)
    def test_perf_logging_habilitado_em_debug(self):
        self.assertTrue(nfe_perf_habilitado())

    @override_settings(DEBUG=False, NFE_PERF_LOGGING=False)
    def test_perf_logging_desabilitado_em_producao(self):
        self.assertFalse(nfe_perf_habilitado())

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_abrir_resumo_nao_gera_checklist_completo(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        with patch(
            'apps.fiscal.validacao_nfe_saida.validar_nfe_saida_para_emissao',
        ) as mock_val:
            conf = montar_conferencia_nfe_saida(nf, modo='abertura', incluir_checklist=False)
            mock_val.assert_not_called()
        self.assertIsNone(conf.get('checklist'))
        self.assertTrue(conf.get('checklist_desatualizado'))

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    @patch('apps.fiscal.nfe_integracao.nfe_xml_preliminar.gerar_xml_nfe_preliminar')
    @patch('apps.fiscal.nfe_saida_preview.gerar_dados_preview_nfe_saida')
    def test_get_conferencia_abertura_nao_gera_xml(self, mock_preview, mock_xml, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        resp = self.client.get(f'/api/nf-saidas/{nf.pk}/conferencia/?modo=abertura')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_preview.assert_not_called()
        mock_xml.assert_not_called()

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_salvar_conferencia_nao_roda_validacao_completa(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        with patch(
            'apps.fiscal.validacao_nfe_saida.validar_nfe_saida_para_emissao',
        ) as mock_val:
            resp = self.client.post(
                f'/api/nf-saidas/{nf.pk}/salvar-conferencia/',
                {'observacoes_internas': 'teste perf 3612'},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
            mock_val.assert_not_called()

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_validar_usa_modo_completo_uma_vez(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        with patch(
            'apps.fiscal.validacao_nfe_saida.validar_nfe_saida_para_emissao',
            wraps=validar_nfe_saida_para_emissao,
        ) as mock_val:
            validar_conferencia_nfe(nf, usuario=self.user)
            completos = [
                c for c in mock_val.call_args_list if (c.kwargs or {}).get('modo') == MODO_VALIDACAO_COMPLETO
            ]
            self.assertEqual(len(completos), 1)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_modo_leve_nao_consulta_cep_remoto(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        with patch('apps.cadastros.endereco_fiscal.validar_endereco_fiscal') as mock_end:
            from apps.cadastros.endereco_fiscal import EnderecoFiscalResult

            mock_end.return_value = EnderecoFiscalResult(
                consistente=True,
                bloqueio_fiscal=False,
                uf_destino='PA',
                alertas=[],
                pendencias=[],
            )
            validar_nfe_saida_para_emissao(nf, modo=MODO_VALIDACAO_LEVE)
            for call in mock_end.call_args_list:
                self.assertFalse(call.kwargs.get('consultar_cep', True))

    @override_settings(FISCAL_PERSISTIR_XML_PRELIMINAR=True)
    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_xml_preliminar_reutiliza_cache(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        xml1 = gerar_xml_nfe_preliminar(nf, persistir=True)
        with patch('apps.fiscal.nfe_saida_preview.gerar_dados_preview_nfe_saida') as mock_preview:
            xml2 = gerar_xml_nfe_preliminar(nf)
            mock_preview.assert_not_called()
        self.assertEqual(xml1, xml2)

    @override_settings(FISCAL_PERSISTIR_XML_PRELIMINAR=True)
    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_xml_cache_invalidado_apos_salvar(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        gerar_xml_nfe_preliminar(nf, persistir=True)
        nf.observacoes_internas = 'invalida cache'
        nf.save(update_fields=['observacoes_internas'])
        invalidar_xml_preliminar_armazenado(nf)
        nf.refresh_from_db()
        self.assertEqual(nf.xml_preliminar, '')

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_validar_nao_altera_transporte(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        nf.modalidade_frete = '0'
        nf.quantidade_volumes = 2
        nf.save(update_fields=['modalidade_frete', 'quantidade_volumes'])
        antes = (nf.modalidade_frete, nf.quantidade_volumes)
        validar_conferencia_nfe(nf, usuario=self.user)
        nf.refresh_from_db()
        depois = (nf.modalidade_frete, nf.quantidade_volumes)
        self.assertEqual(antes, depois)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_preview_danfe_nao_repete_validacao_completa(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        with patch(
            'apps.fiscal.validacao_nfe_saida.validar_nfe_saida_para_emissao',
            wraps=validar_nfe_saida_para_emissao,
        ) as mock_val:
            resp = self.client.get(f'/api/nf-saidas/{nf.pk}/preview-danfe/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content[:200])
            completos = [
                c
                for c in mock_val.call_args_list
                if (c.kwargs or {}).get('modo', MODO_VALIDACAO_COMPLETO) == MODO_VALIDACAO_COMPLETO
            ]
            self.assertLessEqual(len(completos), 0, 'DANFE conferência não deve rodar validação completa')

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_montar_completo_inclui_checklist(self, mock_cep):
        mock_cep.return_value = {'cidade': 'BELEM', 'uf': 'PA', 'cep': '66630-505'}
        nf = self._nf_pronta()
        conf = montar_conferencia_nfe_saida(nf, modo='completo', incluir_checklist=True)
        self.assertIsNotNone(conf.get('checklist'))
        self.assertIn('grupos', conf['checklist'])
