"""ERP 4.0.13.6.11 — Base IBS/CBS 2026 parametrizada com deduções auditáveis."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.nfe_saida_reforma_calculo import aplicar_reforma_tributaria_item
from apps.fiscal.nfe_saida_xml_nfelib import montar_tnfe_oficial, serializar_tnfe
from apps.fiscal.reforma_tributaria.base_ibs_cbs import (
    ContextoBaseIbsCbs,
    calcular_base_ibs_cbs_2026,
    comparar_reforma_xml_externo,
    diagnosticar_base_reforma_cenarios,
)
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa, _regra_sp_pa
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao


REFORMA_BASE = {
    'cst_ibs_cbs': '000',
    'classificacao_tributaria': '000001',
    'aliquota_cbs': '0.9',
    'aliquota_ibs_estadual': '0.1',
}

CTX_FAT13 = ContextoBaseIbsCbs(
    valor_produto=Decimal('12500.00'),
    valor_icms=Decimal('875.00'),
    valor_pis=Decimal('75.56'),
    valor_cofins=Decimal('348.75'),
    valor_ipi=Decimal('0'),
)


def _bloco(modo: str, **extra) -> dict:
    cfg = {**REFORMA_BASE, 'modo_base_ibs_cbs': modo, 'fonte_regra_base_ibs_cbs': 'pendente', **extra}
    return aplicar_reforma_tributaria_item(
        cfg,
        valor_produto=CTX_FAT13.valor_produto,
        valor_icms=CTX_FAT13.valor_icms,
        valor_pis=CTX_FAT13.valor_pis,
        valor_cofins=CTX_FAT13.valor_cofins,
        valor_ipi=CTX_FAT13.valor_ipi,
    )


class BaseIbsCbs4013611UnitTests(TestCase):
    def test_cenario_a_base_cheia(self):
        b = _bloco('BASE_CHEIA_OPERACAO')
        assert b is not None
        self.assertEqual(b['base_ibs_cbs'], '12500.00')
        self.assertEqual(b['valor_cbs'], '112.50')
        self.assertEqual(b['valor_ibs_estadual'], '12.50')
        self.assertEqual(b['valor_total_ibs_cbs'], '125.00')

    def test_cenario_b_base_sem_icms(self):
        b = _bloco('BASE_SEM_ICMS')
        assert b is not None
        self.assertEqual(b['base_ibs_cbs'], '11625.00')
        self.assertEqual(b['valor_cbs'], '104.63')
        self.assertEqual(b['valor_ibs_estadual'], '11.63')
        self.assertEqual(b['valor_total_ibs_cbs'], '116.26')

    def test_cenario_c_base_sem_icms_pis_cofins(self):
        b = _bloco('BASE_SEM_ICMS_PIS_COFINS')
        assert b is not None
        self.assertEqual(b['base_ibs_cbs'], '11200.69')
        self.assertEqual(b['valor_cbs'], '100.81')
        self.assertEqual(b['valor_ibs_estadual'], '11.20')
        self.assertEqual(b['valor_total_ibs_cbs'], '112.01')

    def test_snapshot_guarda_formula_e_deducoes(self):
        b = _bloco('BASE_SEM_ICMS_PIS_COFINS')
        assert b is not None
        self.assertEqual(b['formula_base_ibs_cbs'], 'vProd - vICMS - vPIS - vCOFINS')
        self.assertEqual(b['valor_deduzido_icms'], '875.00')
        self.assertEqual(b['valor_deduzido_pis'], '75.56')
        self.assertEqual(b['valor_deduzido_cofins'], '348.75')
        self.assertEqual(b['fonte_regra_base_ibs_cbs'], 'pendente')
        self.assertEqual(b['status_base_reforma'], 'pendente_confirmacao')

    def test_diagnostico_cenarios_comparativo(self):
        cenarios = diagnosticar_base_reforma_cenarios(
            CTX_FAT13,
            aliquota_cbs='0.9',
            aliquota_ibs_uf='0.1',
        )
        self.assertEqual(len(cenarios), 4)
        c = {x['cenario']: x for x in cenarios}
        self.assertEqual(c['A']['base_ibs_cbs'], '12500.00')
        self.assertEqual(c['B']['base_ibs_cbs'], '11625.00')
        self.assertEqual(c['C']['base_ibs_cbs'], '11200.69')

    def test_calcular_base_modo_oficial_2026(self):
        res = calcular_base_ibs_cbs_2026(
            CTX_FAT13,
            {'modo_base_ibs_cbs': 'BASE_OFICIAL_2026', 'fonte_regra_base_ibs_cbs': 'oficial'},
        )
        self.assertEqual(res.base_ibs_cbs, Decimal('11200.69'))
        self.assertEqual(res.status_base_reforma, 'confirmada')

    def test_nao_altera_icms_pis_cofins_no_bloco_reforma(self):
        b = _bloco('BASE_SEM_ICMS_PIS_COFINS')
        assert b is not None
        self.assertNotIn('valor_icms', b)
        self.assertNotIn('valor_pis', b)


class BaseIbsCbs4013611IntegracaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3611', 'nfe3611@test.com', 'x')
        regra = _regra_sp_pa()
        regra.reforma_tributaria = {
            **REFORMA_BASE,
            'modo_base_ibs_cbs': 'BASE_SEM_ICMS_PIS_COFINS',
            'fonte_regra_base_ibs_cbs': 'pendente',
        }
        regra.save(update_fields=['reforma_tributaria'])

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_xml_serializa_base_do_snapshot(self, mock_cep):
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
        item = nf.itens.first()
        ref = (item.snapshot_fiscal or {}).get('reforma_tributaria') or {}
        self.assertEqual(ref.get('modo_base_ibs_cbs'), 'BASE_SEM_ICMS_PIS_COFINS')
        self.assertIn('formula_base_ibs_cbs', ref)

        dados = gerar_dados_preview_nfe_saida(nf, incluir_validacao_emissao=False)
        tnfe = montar_tnfe_oficial(dados, nfe_saida=nf)
        xml = serializar_tnfe(tnfe, pretty=False)
        self.assertIn('IBSCBS', xml)
        self.assertIn('IBSCBSTot', xml)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_checklist_alerta_regra_pendente_homolog(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        with override_settings(REFORMA_TRIBUTARIA_NFE_MODO='homologacao'):
            val = validar_nfe_saida_para_emissao(nf)
        codigos = [
            p.get('codigo')
            for g in (val.get('grupos') or {}).values()
            for p in g
        ]
        self.assertIn('REFORMA_BASE_FONTE_PENDENTE', codigos)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_producao_bloqueia_regra_pendente(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        with override_settings(REFORMA_TRIBUTARIA_NFE_MODO='producao', REFORMA_TRIBUTARIA_NFE_ENABLED=True):
            val = validar_nfe_saida_para_emissao(nf)
        pend = [
            p for g in (val.get('grupos') or {}).values() for p in g if p.get('tipo') == 'PENDENCIA'
        ]
        codigos = [p.get('codigo') for p in pend]
        self.assertIn('REFORMA_BASE_FONTE_PENDENTE', codigos)


class ComparadorXmlReformaTests(TestCase):
    def test_comparador_detecta_divergencia_base(self):
        xml_a = '<vProd>12500.00</vProd><vICMS>875.00</vICMS><vBC>12500.00</vBC>'
        xml_b = '<vProd>12500.00</vProd><vICMS>875.00</vICMS><vBC>11625.00</vBC>'
        r = comparar_reforma_xml_externo(xml_a, xml_b)
        self.assertEqual(r['resultado'], 'divergente')
