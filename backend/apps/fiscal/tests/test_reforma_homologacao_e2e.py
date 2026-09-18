"""Teste E2E validação IBS/CBS homologação - NF-e tpAmb=2."""

from __future__ import annotations

import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_saida_xml_nfelib import montar_tnfe_oficial, serializar_tnfe
from apps.fiscal.reforma_tributaria.xml import (
    validar_reforma_serializada_em_xml,
)
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa, _regra_sp_pa


def _xml_tem_tag(xml: str, tag: str) -> bool:
    return bool(re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(tag)}\b', xml, re.IGNORECASE))


def _xml_valor_tag(xml: str, tag: str) -> str | None:
    m = re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(tag)}>([^<]+)</', xml, re.IGNORECASE)
    return m.group(1) if m else None


REFORMA_HOMOLOG_SETTINGS = {
    'REFORMA_TRIBUTARIA_NFE_ENABLED': True,
    'REFORMA_TRIBUTARIA_NFE_MODO': 'homologacao',
    'REFORMA_TRIBUTARIA_NFE_INCLUIR_XML': True,
    'REFORMA_TRIBUTARIA_NFE_INCLUIR_DANFE': False,
    'REFORMA_TRIBUTARIA_NFE_AMBIENTE_HOMOLOGACAO': True,
    'REFORMA_TRIBUTARIA_NFE_PRODUCAO_BLOQUEADA': True,
}


@override_settings(**REFORMA_HOMOLOG_SETTINGS)
@patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
class ReformaHomologacaoE2ETests(TestCase):
    """Validação ponta a ponta do XML de homologação com Reforma Tributária."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('reforma_e2e', 'reforma_e2e@test.com', 'x')
        regra = _regra_sp_pa()
        regra.reforma_tributaria = {
            'cst_ibs_cbs': '000',
            'classificacao_tributaria': '000001',
            'aliquota_ibs_estadual': '0,1',
            'aliquota_cbs': '0,9',
        }
        regra.save(update_fields=['reforma_tributaria'])

    def _mock_cep(self):
        return {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }

    def _preparar_nf(self):
        mock_cep = self._mock_cep()
        with patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=mock_cep):
            nf, nf_item = _nf_pa()
            nf.ambiente_emissao = 'homologacao'
            nf.save(update_fields=['ambiente_emissao'])
            # Ensure emitente has IE - use pedido.empresa_emitente since NF-e may not have empresa_emitente set
            if nf.pedido_venda_id and nf.pedido_venda.empresa_emitente_id:
                emp = nf.pedido_venda.empresa_emitente
                if not (emp.ie or '').strip():
                    emp.ie = '123456789012'
                    emp.save(update_fields=['ie'])
                # Re-fetch to ensure fresh data
                emp.refresh_from_db()
                nf.refresh_from_db()
            aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
            nf_item.refresh_from_db()
            return nf, nf_item

    def _gerar_xml(self, nf, nf_item):
        dados = gerar_dados_preview_nfe_saida(nf)
        self.assertFalse(dados.get('bloqueado'))
        for linha in dados.get('itens') or []:
            if linha.get('item_id') == nf_item.pk:
                linha['snapshot_fiscal'] = nf_item.snapshot_fiscal or {}

        tnfe = montar_tnfe_oficial(dados, nfe_saida=nf)
        return serializar_tnfe(tnfe, pretty=False)

    def test_xml_homologacao_tpamb_2_contem_ibscbs_ibscbstot(self, mock_cep):
        """XML de homologação deve ter tpAmb=2, IBSCBS e IBSCBSTot com valores corretos."""
        mock_cep.return_value = self._mock_cep()
        nf, nf_item = self._preparar_nf()
        xml = self._gerar_xml(nf, nf_item)

        # 1. tpAmb = 2 (homologação)
        self.assertEqual(_xml_valor_tag(xml, 'tpAmb'), '2')

        # 2. IBSCBS presente no item
        self.assertTrue(_xml_tem_tag(xml, 'ibscbs'), 'IBSCBS não encontrado no XML')

        # 3. CST = 000
        cst_matches = re.findall(r'<(?:[\w]*:)?cst>([^<]+)</(?:[\w]*:)?cst>', xml, re.IGNORECASE)
        ibscbs_cst = next((c for c in cst_matches if c == '000'), None)
        self.assertIsNotNone(ibscbs_cst, f'CST 000 não encontrado. CSTs: {cst_matches}')

        # 4. cClassTrib = 000001
        cclass_matches = re.findall(r'<(?:[\w]*:)?cclasstrib>([^<]+)</(?:[\w]*:)?cclasstrib>', xml, re.IGNORECASE)
        ibscbs_cclass = cclass_matches[0] if cclass_matches else None
        self.assertEqual(ibscbs_cclass, '000001', f'cClassTrib incorreto: {ibscbs_cclass}')

        # 5. gIBSCBS presente
        self.assertTrue(_xml_tem_tag(xml, 'gibscbs'), 'gIBSCBS não encontrado')

        # 6. vBC presente
        vbc = _xml_valor_tag(xml, 'vBC')
        self.assertIsNotNone(vbc, 'vBC não encontrado')
        self.assertEqual(vbc, '500.00')

        # 7. gIBSUF presente
        self.assertTrue(_xml_tem_tag(xml, 'gibsuf'), 'gIBSUF não encontrado')
        pibsuf = _xml_valor_tag(xml, 'pIBSUF')
        vibsuf = _xml_valor_tag(xml, 'vIBSUF')
        self.assertEqual(pibsuf, '0.1000', f'pIBSUF: {pibsuf}')
        self.assertEqual(vibsuf, '0.50', f'vIBSUF: {vibsuf}')

        # 8. gIBSMun presente (pode ser 0)
        self.assertTrue(_xml_tem_tag(xml, 'gibsmun'), 'gIBSMun não encontrado')
        vibsmun = _xml_valor_tag(xml, 'vIBSMun')
        self.assertEqual(vibsmun, '0.00', f'vIBSMun: {vibsmun}')

        # 9. gCBS presente
        self.assertTrue(_xml_tem_tag(xml, 'gcbs'), 'gCBS não encontrado')
        pcbs = _xml_valor_tag(xml, 'pCBS')
        vcbs = _xml_valor_tag(xml, 'vCBS')
        self.assertEqual(pcbs, '0.9000', f'pCBS: {pcbs}')
        self.assertEqual(vcbs, '4.50', f'vCBS: {vcbs}')

        # 10. IBSCBSTot presente
        self.assertTrue(_xml_tem_tag(xml, 'ibscbstot'), 'IBSCBSTot não encontrado')

        # Validação numérica dos totais
        vbc_total = _xml_valor_tag(xml, 'vBCIBSCBS')
        self.assertEqual(vbc_total, '500.00', f'vBCIBSCBS total: {vbc_total}')

        # Validação via validador
        chk = validar_reforma_serializada_em_xml(
            xml,
            itens=[{'snapshot_fiscal': nf_item.snapshot_fiscal or {}}],
        )
        self.assertTrue(any(c['codigo'] == 'REFORMA_XML_OK' for c in chk), f'Validação falhou: {chk}')

    def test_checklist_flags_ligadas_xml_com_reforma_retorna_reforma_xml_ok(self, mock_cep):
        """Flags ligadas + snapshot calculada + XML com Reforma devem gerar REFORMA_XML_OK."""
        mock_cep.return_value = self._mock_cep()
        nf, nf_item = self._preparar_nf()
        xml = self._gerar_xml(nf, nf_item)

        from apps.fiscal.nfe_saida_checklist_homologacao import validar_prontidao_nfe_homologacao
        with (
            patch(
                'apps.fiscal.nfe_integracao.nfe_xml_preliminar.pode_gerar_xml_preliminar',
                return_value=(True, []),
            ),
            patch(
                'apps.fiscal.nfe_integracao.nfe_xml_preliminar.gerar_xml_nfe_preliminar',
                return_value=xml.encode('utf-8'),
            ),
        ):
            resultado = validar_prontidao_nfe_homologacao(nfe_saida=nf)

        codigos = {item['codigo'].upper() for item in resultado['itens']}
        self.assertIn('REFORMA_XML_OK', codigos, f'REFORMA_XML_OK não encontrado. Itens: {resultado["itens"]}')

    def test_flags_ligadas_snapshot_calculada_xml_sem_reforma_retorna_reforma_ausente_xml(self, mock_cep):
        """Flags ligadas + snapshot calculada + XML sem Reforma devem gerar REFORMA_AUSENTE_XML."""
        mock_cep.return_value = self._mock_cep()
        _, nf_item = self._preparar_nf()
        xml_sem_reforma = '<NFe><infNFe><total><ICMSTot /></total></infNFe></NFe>'

        chk = validar_reforma_serializada_em_xml(
            xml_sem_reforma,
            itens=[{'snapshot_fiscal': nf_item.snapshot_fiscal or {}}],
        )

        self.assertIn('REFORMA_AUSENTE_XML', {item['codigo'] for item in chk})

    def test_flags_desligadas_omitem_reforma_sem_reforma_ausente_xml(self, mock_cep):
        """Flags desligadas omitem Reforma pelo gate, sem gerar REFORMA_AUSENTE_XML."""
        mock_cep.return_value = self._mock_cep()
        nf, nf_item = self._preparar_nf()

        with override_settings(
            REFORMA_TRIBUTARIA_NFE_ENABLED=False,
            REFORMA_TRIBUTARIA_NFE_MODO='pesquisa',
            REFORMA_TRIBUTARIA_NFE_INCLUIR_XML=False,
        ):
            xml = self._gerar_xml(nf, nf_item)
            chk = validar_reforma_serializada_em_xml(
                xml,
                itens=[{'snapshot_fiscal': nf_item.snapshot_fiscal or {}}],
            )

        self.assertFalse(_xml_tem_tag(xml, 'ibscbs'), 'IBSCBS não deve ser serializado com flags desligadas')
        self.assertFalse(_xml_tem_tag(xml, 'ibscbstot'), 'IBSCBSTot não deve ser serializado com flags desligadas')
        self.assertNotIn('REFORMA_AUSENTE_XML', {item['codigo'] for item in chk})


if __name__ == '__main__':
    import unittest
    unittest.main()
