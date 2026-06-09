"""ERP 4.0.13.6.9 — Reforma Tributária serializada em todos os XMLs NF-e."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_saida_xml_nfelib import montar_tnfe_oficial, serializar_tnfe
from apps.fiscal.reforma_tributaria.xml import (
    build_reforma_tributaria_item_bindings,
    build_reforma_tributaria_total_bindings,
    nf_tem_reforma_calculada,
    validar_reforma_serializada_em_xml,
    xml_contem_reforma_tributaria,
)
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa, _regra_sp_pa
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao


def _xml_tem_tag(xml: str, tag: str) -> bool:
    return bool(re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(tag)}\b', xml, re.IGNORECASE))


def _xml_valor_tag(xml: str, tag: str) -> str | None:
    m = re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(tag)}>([^<]+)</', xml, re.IGNORECASE)
    return m.group(1) if m else None


def _linha_rascunho_fat_12() -> dict:
    return {
        'n_item': '1',
        'item_id': 1,
        'c_prod': 'FLANGE1',
        'x_prod': 'FLANGE SW ACO CARBONO ANSI 150# RF SCH 160 1.1/2"',
        'ncm': '73079100',
        'cfop': '6102',
        'u_com': 'UN',
        'q_com': '50',
        'v_un_com': '250.00',
        'v_prod': '12500.00',
        'snapshot_fiscal': {
            'ncm': '73079100',
            'cfop': '6102',
            'cst_icms': '00',
            'aliquota_icms': '12',
            'base_icms': '12500.00',
            'valor_icms': '1500.00',
            'cst_pis': '01',
            'aliquota_pis': '0.65',
            'valor_pis': '81.25',
            'cst_cofins': '01',
            'aliquota_cofins': '3',
            'valor_cofins': '375.00',
            'reforma_tributaria': {
                'cst_ibs_cbs': '000',
                'classificacao_tributaria': '000001',
                'aliquota_cbs': '0.9',
                'aliquota_ibs_estadual': '0.1',
                'base_cbs': '12500.00',
                'valor_cbs': '112.50',
                'base_ibs_estadual': '12500.00',
                'valor_ibs_estadual': '12.50',
                'valor_ibs_municipal': '0.00',
                'valor_total_ibs_cbs': '125.00',
            },
        },
    }


def _dados_xml_base() -> dict:
    return {
        'nfe_saida_id': 12,
        'numero': 'RASCUNHO-FAT-12',
        'ide': {'c_uf': '35', 'nat_op': 'Venda', 'tp_nf': '1', 'id_dest': '2', 'c_mun_fg': '3550308'},
        'emitente': {
            'cnpj': '03999102000150',
            'x_nome': 'Emitente SP',
            'ie': '123456789',
            'crt': '3',
            'uf': 'SP',
            'cidade': 'SAO PAULO',
            'c_mun': '3550308',
            'logradouro': 'Rua A',
            'numero': '1',
            'bairro': 'Centro',
            'cep': '01001000',
        },
        'destinatario': {
            'cnpj': '00000000000191',
            'x_nome': 'Dest PA',
            'uf': 'PA',
            'cidade': 'BELEM',
            'cep': '66630505',
            'logradouro': 'AV SALGADO FILHO',
            'numero': 'S/N',
            'bairro': 'VAL-DE-CAES',
        },
        'itens': [_linha_rascunho_fat_12()],
        'totais': {
            'v_prod': '12500.00',
            'v_nf': '12500.00',
            'v_icms': '1500.00',
            'v_pis': '81.25',
            'v_cofins': '375.00',
        },
        }


REFORMA_XML_HOMOLOG_SETTINGS = {
    'REFORMA_TRIBUTARIA_NFE_ENABLED': True,
    'REFORMA_TRIBUTARIA_NFE_MODO': 'homologacao',
    'REFORMA_TRIBUTARIA_NFE_INCLUIR_XML': True,
}


@override_settings(**REFORMA_XML_HOMOLOG_SETTINGS)
@unittest.skipUnless(nfelib_disponivel(), 'nfelib não instalado')
class ReformaXmlBindings401369Tests(TestCase):
    def test_item_bindings_valores_rascunho_fat_12(self):
        linha = _linha_rascunho_fat_12()
        ibscbs = build_reforma_tributaria_item_bindings(linha)
        self.assertIsNotNone(ibscbs)
        assert ibscbs is not None
        self.assertEqual(ibscbs.CST, '000')
        self.assertEqual(ibscbs.cClassTrib, '000001')
        g = ibscbs.gIBSCBS
        assert g is not None
        self.assertEqual(g.vBC, '12500.00')
        self.assertEqual(g.gCBS.vCBS, '112.50')
        self.assertEqual(g.gCBS.pCBS, '0.9000')
        self.assertEqual(g.gIBSUF.vIBSUF, '12.50')
        self.assertEqual(g.gIBSUF.pIBSUF, '0.1000')

    def test_total_bindings_agrega_itens(self):
        tot = build_reforma_tributaria_total_bindings([_linha_rascunho_fat_12()])
        self.assertIsNotNone(tot)
        assert tot is not None
        self.assertEqual(tot.vBCIBSCBS, '12500.00')
        self.assertEqual(tot.gCBS.vCBS, '112.50')
        self.assertEqual(tot.gIBS.gIBSUF.vIBSUF, '12.50')

    def test_sem_reforma_quando_snapshot_vazio(self):
        linha = dict(_linha_rascunho_fat_12())
        linha['snapshot_fiscal'] = {'ncm': '73079100'}
        self.assertIsNone(build_reforma_tributaria_item_bindings(linha))
        self.assertFalse(nf_tem_reforma_calculada([linha]))


@override_settings(**REFORMA_XML_HOMOLOG_SETTINGS)
@unittest.skipUnless(nfelib_disponivel(), 'nfelib não instalado')
class ReformaXmlCentral401369Tests(TestCase):
    def test_xml_oficial_contem_ibscbs_e_cmun_belem(self):
        dados = _dados_xml_base()
        tnfe = montar_tnfe_oficial(dados)
        xml = serializar_tnfe(tnfe, pretty=False).lower()
        self.assertTrue(_xml_tem_tag(xml, 'ibscbs'))
        self.assertTrue(_xml_tem_tag(xml, 'ibscbstot'))
        self.assertEqual(_xml_valor_tag(xml, 'vcbs'), '112.50')
        self.assertEqual(_xml_valor_tag(xml, 'vibsuf'), '12.50')
        idx_dest = xml.find('enderdest')
        self.assertGreater(idx_dest, 0)
        trecho_dest = xml[idx_dest : idx_dest + 500]
        self.assertIn('1501402', trecho_dest)
        self.assertNotIn('3550308', trecho_dest)

    def test_mesma_reforma_em_duas_geracoes(self):
        dados = _dados_xml_base()
        xml_a = serializar_tnfe(montar_tnfe_oficial(dict(dados)), pretty=False).lower()
        xml_b = serializar_tnfe(montar_tnfe_oficial(dict(dados)), pretty=False).lower()
        self.assertEqual(_xml_valor_tag(xml_a, 'vcbs'), _xml_valor_tag(xml_b, 'vcbs'))
        self.assertEqual(_xml_valor_tag(xml_a, 'vibsuf'), _xml_valor_tag(xml_b, 'vibsuf'))

    def test_cmun_inconsistente_bloqueia(self):
        from apps.fiscal.nfe_saida_xml_nfelib import NFeXmlNfelibError, preparar_dados_serializacao_xml

        dados = _dados_xml_base()
        dados['destinatario']['c_mun'] = '3550308'
        with self.assertRaises(NFeXmlNfelibError) as ctx:
            preparar_dados_serializacao_xml(dados)
        self.assertIn('incompatível', str(ctx.exception).lower())

    def test_icms_pis_cofins_nao_alterados(self):
        dados = _dados_xml_base()
        xml = serializar_tnfe(montar_tnfe_oficial(dados), pretty=False).lower()
        self.assertEqual(_xml_valor_tag(xml, 'vicms'), '1500.00')
        self.assertEqual(_xml_valor_tag(xml, 'vpis'), '81.25')
        self.assertEqual(_xml_valor_tag(xml, 'vcofins'), '375.00')
        self.assertEqual(_xml_valor_tag(xml, 'vprod'), '12500.00')
        self.assertEqual(_xml_valor_tag(xml, 'vnf'), '12500.00')


@override_settings(**REFORMA_XML_HOMOLOG_SETTINGS)
class NFeReformaIntegracao401369Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe401369', 'nfe401369@test.com', 'x')
        regra = _regra_sp_pa()
        regra.reforma_tributaria = {
            'cst_ibs_cbs': '000',
            'classificacao_tributaria': '000001',
            'aliquota_ibs_estadual': '0,1',
            'aliquota_cbs': '0,9',
        }
        regra.save(update_fields=['reforma_tributaria'])

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_atualizar_fiscal_e_xml_preliminar_com_reforma(self, mock_cep):
        if not nfelib_disponivel():
            self.skipTest('nfelib não instalado')
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': 'AV',
            'bairro': 'X',
            'complemento': '',
        }
        nf, nf_item = _nf_pa()
        if nf.empresa_emitente_id:
            emp = nf.empresa_emitente
            if not (emp.ie or '').strip():
                emp.ie = '123456789012'
                emp.save(update_fields=['ie'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        ref = (nf_item.snapshot_fiscal or {}).get('reforma_tributaria') or {}
        self.assertEqual(ref.get('valor_cbs'), '4.50')

        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertFalse(dados.get('bloqueado'))
        for linha in dados.get('itens') or []:
            if linha.get('item_id') == nf_item.pk:
                linha['snapshot_fiscal'] = nf_item.snapshot_fiscal or {}
        xml = serializar_tnfe(montar_tnfe_oficial(dados, nfe_saida=nf), pretty=False).lower()
        self.assertTrue(xml_contem_reforma_tributaria(xml))
        self.assertTrue(_xml_tem_tag(xml, 'ibscbs'))
        chk = validar_reforma_serializada_em_xml(
            xml,
            itens=[{'snapshot_fiscal': nf_item.snapshot_fiscal or {}}],
        )
        self.assertTrue(any(c['codigo'] == 'REFORMA_XML_OK' for c in chk))

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_validacao_detecta_reforma_no_xml(self, mock_cep):
        if not nfelib_disponivel():
            self.skipTest('nfelib não instalado')
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        if nf.empresa_emitente_id:
            emp = nf.empresa_emitente
            if not (emp.ie or '').strip():
                emp.ie = '123456789012'
                emp.save(update_fields=['ie'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=nf.pk)
        val = validar_nfe_saida_para_emissao(nf)
        codigos = [p.get('codigo') for g in val.get('grupos', {}).values() for p in g]
        self.assertIn('REFORMA_XML_OK', codigos)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_xml_destinatario_cmun_belem_pa(self, mock_cep):
        if not nfelib_disponivel():
            self.skipTest('nfelib não instalado')
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        if nf.empresa_emitente_id:
            emp = nf.empresa_emitente
            if not (emp.ie or '').strip():
                emp.ie = '123456789012'
                emp.save(update_fields=['ie'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertFalse(dados.get('bloqueado'))
        xml = serializar_tnfe(montar_tnfe_oficial(dados, nfe_saida=nf), pretty=False)
        idx_dest = xml.lower().find('enderdest')
        self.assertGreater(idx_dest, 0)
        trecho = xml[idx_dest : idx_dest + 400].lower()
        self.assertIn('1501402', trecho)
        self.assertNotIn('3550308', trecho)
