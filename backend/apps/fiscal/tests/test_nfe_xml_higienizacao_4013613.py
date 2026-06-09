"""ERP 4.0.13.6.13 — Higienização XML de transmissão NF-e."""

from __future__ import annotations

import re
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError, gerar_xml_oficial_emissao
from apps.fiscal.nfe_emissao.xml_serializacao import formatar_dh_emi
from apps.fiscal.nfe_xml_higienizacao import (
    montar_resumo_higienizacao_xml,
    normalizar_ie_xml,
    validar_higienizacao_xml_transmissao,
)
from apps.fiscal.nfe_xml_transmissao import (
    gerar_xml_preview_conferencia,
    gerar_xml_transmissao_homologacao,
    montar_payload_xml_transmissao_homologacao,
)
from apps.fiscal.tests.test_nfe_atualizar_fiscal_cenario_401365 import _nf_pa
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao


def _confirmar_indicadores(nf: NFeSaida) -> None:
    nf.ind_final = '1'
    nf.ind_pres = '1'
    nf.indicadores_fiscais_confirmados = True
    nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])


def _reservar_e_confirmar(nf: NFeSaida, user) -> NFeSaida:
    reservar_numeracao_nfe(nf, ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO, usuario=user)
    nf.refresh_from_db()
    _confirmar_indicadores(nf)
    return nf


def _mock_cep_belem():
    return {
        'cep': '66630505',
        'logradouro': 'AV SALGADO FILHO',
        'bairro': 'VAL-DE-CAES',
        'localidade': 'BELEM',
        'uf': 'PA',
        'ibge': '1501402',
    }


class NFeXmlHigienizacao4013613UnitTests(TestCase):
    def setUp(self):
        self._cep_patcher = patch(
            'apps.cadastros.endereco_fiscal.consultar_cep_viacep',
            return_value=_mock_cep_belem(),
        )
        self._cep_patcher.start()
        self.addCleanup(self._cep_patcher.stop)

    def test_normalizar_ie_remove_mascara(self):
        self.assertEqual(normalizar_ie_xml('152.451.500.11'), '15245150011')
        self.assertEqual(normalizar_ie_xml('15-220462-8'), '152204628')
        self.assertEqual(normalizar_ie_xml('796.823.082.11'), '79682308211')
        self.assertEqual(normalizar_ie_xml('ISENTO'), 'ISENTO')

    def test_formatar_dh_emi_com_timezone_sem_micros(self):
        dh = formatar_dh_emi()
        self.assertRegex(dh, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$')
        self.assertNotIn('.', dh)

    def test_preview_contem_nfe_preview(self):
        nf, _ = _nf_pa()
        data = gerar_xml_preview_conferencia(nf)
        self.assertIn('NFePREVIEW', data['xml'])
        self.assertIn('NÃO TRANSMITIR', data['xml'].upper())

    def test_validar_higienizacao_rejeita_preview(self):
        xml_preview = (
            '<?xml version="1.0"?><NFe><infNFe Id="NFePREVIEW13">'
            '<ide><dhEmi>2026-05-29T15:43:25.18799</dhEmi></ide></infNFe></NFe>'
        )
        itens = validar_higienizacao_xml_transmissao(xml_preview)
        codigos = {i['codigo'] for i in itens}
        self.assertIn('XML_ID_PREVIEW', codigos)
        self.assertIn('XML_DHEMI_MICROS', codigos)

    def test_validar_higienizacao_ie_com_mascara(self):
        xml = '<?xml version="1.0"?><NFe><infNFe Id="NFe35260512345678000199550090000000021000000021"><emit><IE>152.451.500.11</IE></emit></infNFe></NFe>'
        codigos = {i['codigo'] for i in validar_higienizacao_xml_transmissao(xml)}
        self.assertIn('XML_IE_COM_MASCARA', codigos)

    def test_montar_resumo_sem_xml_aguarda_geracao(self):
        nf, _ = _nf_pa()
        res = montar_resumo_higienizacao_xml(nf)
        self.assertFalse(res['tem_xml_transmissao'])
        self.assertFalse(res['aprovado'])


class NFeXmlHigienizacao4013613EmissaoTests(TestCase):
    def setUp(self):
        self._cep_patcher = patch(
            'apps.cadastros.endereco_fiscal.consultar_cep_viacep',
            return_value=_mock_cep_belem(),
        )
        self._cep_patcher.start()
        self.addCleanup(self._cep_patcher.stop)
        self.user = get_user_model().objects.create_user(
            f'nfe4013613_{uuid.uuid4().hex[:8]}',
            'nfe4013613@test.com',
            'x',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.empresa = self.pedido.empresa_emitente
        _confirmar_indicadores(self.nf)

    def _xml_transmissao(self) -> str:
        _reservar_e_confirmar(self.nf, self.user)
        return gerar_xml_transmissao_homologacao(self.nf).decode('utf-8')

    def test_xml_transmissao_sem_preview(self):
        xml = self._xml_transmissao()
        self.assertNotIn('NFePREVIEW', xml)
        self.assertNotIn('NÃO TRANSMITIR', xml.upper())
        self.assertNotIn('NAO TRANSMITIR', xml.upper())
        self.assertRegex(xml, r'Id="NFe\d{44}"')
        self.assertRegex(xml, r'<dhEmi>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}</dhEmi>')

    def test_xml_transmissao_usa_chave_real(self):
        xml = self._xml_transmissao()
        chave = self.nf.chave_acesso
        self.assertIn(f'Id="NFe{chave}"', xml)

    def test_xml_transmissao_ie_sem_mascara(self):
        xml = self._xml_transmissao()
        self.assertFalse(re.search(r'<IE>[^<]*[.\-/][^<]*</IE>', xml, re.I))

    def test_xml_transmissao_cnpj_cep_somente_digitos(self):
        xml = self._xml_transmissao()
        for tag in ('CNPJ', 'CEP'):
            for m in re.finditer(rf'<{tag}>([^<]+)</{tag}>', xml, re.I):
                self.assertTrue(m.group(1).isdigit(), f'{tag}={m.group(1)}')

    def test_xml_transmissao_preserva_ind_final_ind_pres(self):
        self.nf.ind_final = '0'
        self.nf.ind_pres = '2'
        self.nf.indicadores_fiscais_confirmados = True
        self.nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
        xml = self._xml_transmissao()
        self.assertIn('<indFinal>0</indFinal>', xml)
        self.assertIn('<indPres>2</indPres>', xml)

    def test_preview_e_transmissao_diferem_apenas_marcas(self):
        _reservar_e_confirmar(self.nf, self.user)
        preview = gerar_xml_preview_conferencia(self.nf)['xml']
        trans = gerar_xml_transmissao_homologacao(self.nf).decode('utf-8')
        self.assertIn('NFePREVIEW', preview)
        self.assertNotIn('NFePREVIEW', trans)
        self.assertNotIn('NÃO TRANSMITIR', trans.upper())

    def test_bloqueia_transmissao_sem_indicadores_confirmados(self):
        _reservar_e_confirmar(self.nf, self.user)
        self.nf.indicadores_fiscais_confirmados = False
        self.nf.save(update_fields=['indicadores_fiscais_confirmados'])
        with self.assertRaises(NFeXmlEmissaoError):
            gerar_xml_transmissao_homologacao(self.nf)

    def test_bloqueia_transmissao_sem_chave(self):
        with self.assertRaises(NFeXmlEmissaoError) as ctx:
            gerar_xml_oficial_emissao(self.nf)
        self.assertIn('chave de acesso', str(ctx.exception).lower())

    def test_checklist_bloqueia_indicadores_nao_confirmados(self):
        reservar_numeracao_nfe(self.nf, ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO, usuario=self.user)
        self.nf.refresh_from_db()
        self.nf.indicadores_fiscais_confirmados = False
        self.nf.save(update_fields=['indicadores_fiscais_confirmados'])
        val = validar_nfe_saida_para_emissao(self.nf, modo='completo')
        codigos = {i['codigo'] for g in val['grupos'].values() for i in g}
        self.assertIn('INDICADORES_NAO_CONFIRMADOS', codigos)

    def test_endpoint_xml_transmissao_homologacao(self):
        _reservar_e_confirmar(self.nf, self.user)
        res = self.client.post(f'/api/nf-saidas/{self.nf.pk}/xml-transmissao-homologacao/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        body = res.json()
        self.assertNotIn('NFePREVIEW', body['xml'])
        self.assertTrue(body['higienizacao']['aprovado'])

    def test_endpoint_validar_higienizacao_xml(self):
        _reservar_e_confirmar(self.nf, self.user)
        payload = montar_payload_xml_transmissao_homologacao(self.nf)
        res = self.client.post(
            f'/api/nf-saidas/{self.nf.pk}/validar-higienizacao-xml/',
            {'xml': payload['xml']},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertTrue(res.json()['aprovado'])

    def test_bloqueia_ie_emitente_invalida(self):
        emp = self.nf.pedido_venda.empresa_emitente
        emp.ie = '1'
        emp.save(update_fields=['ie'])
        _reservar_e_confirmar(self.nf, self.user)
        xml = gerar_xml_transmissao_homologacao(self.nf).decode('utf-8')
        codigos = {i['codigo'] for i in validar_higienizacao_xml_transmissao(xml, nfe_saida=self.nf)}
        self.assertIn('XML_IE_EMITENTE_INVALIDA', codigos)

    @patch('apps.fiscal.nfe_xml_transmissao.validar_higienizacao_xml_transmissao')
    def test_payload_bloqueia_xsd_falha(self, mock_validar):
        _reservar_e_confirmar(self.nf, self.user)
        mock_validar.return_value = [
            {'tipo': 'PENDENCIA', 'codigo': 'XSD_FAIL', 'grupo': 'higienizacao_xml', 'mensagem': 'XSD inválido'},
        ]
        with self.assertRaises(NFeXmlEmissaoError):
            montar_payload_xml_transmissao_homologacao(self.nf)
