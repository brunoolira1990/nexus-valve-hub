"""Regressão: conferência NF-e não deve entrar em recursão infinita na validação."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa, _regra_sp_pa
from apps.regras_fiscais.models import RegraFiscalSaida


class NFeConferenciaSemRecursao401369Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe369r', 'nfe369r@test.com', 'x')
        regra = _regra_sp_pa()
        regra.reforma_tributaria = {
            'cst_ibs_cbs': '000',
            'classificacao_tributaria': '000001',
            'aliquota_ibs_estadual': '0,1',
            'aliquota_cbs': '0,9',
        }
        regra.save(update_fields=['reforma_tributaria'])

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_montar_conferencia_retorna_sem_recursao(self, mock_cep):
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
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)

        conf = montar_conferencia_nfe_saida(nf, modo='completo', incluir_checklist=True)
        self.assertIn('nfe', conf)
        self.assertIn('checklist', conf)
        codigos = [
            p.get('codigo')
            for g in (conf.get('checklist') or {}).get('grupos', {}).values()
            for p in g
        ]
        self.assertNotIn('REFORMA_XML_GERACAO_FALHOU', codigos)
