"""NF-e 4.0.2 — validação XSD, schema XML e rejeição 225."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_xml
from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.schema_validacao import validar_emissao_completa, validar_xml_nfe_schema
from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, emitir_nfe_homologacao, validar_xml_nfe_saida_schema
from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao
from apps.fiscal.nfe_emissao.xml_serializacao import normalizar_xml_nfe, xml_contem_grupo_pag, xml_root_e_nfe
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao
from apps.produtos.models import FamiliaProduto, Produto

from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import (
    _criar_pfx,
    _ensure_numeracao_empresa,
    _pedido_nf,
    _xml_tem_tag,
)


class NFeSaida402SchemaXmlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username=f'schema_{uuid.uuid4().hex[:8]}',
            password='test123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        _, _, self.nf = _pedido_nf()
        self.nf.ind_final = '1'
        self.nf.ind_pres = '1'
        self.nf.indicadores_fiscais_confirmados = True
        self.nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
        marcar_nfe_pronta_para_emissao(self.nf, usuario=self.user)
        reservar_numeracao_nfe(self.nf, ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO, usuario=self.user)
        self.nf.refresh_from_db()
        self.nf.indicadores_fiscais_confirmados = True
        self.nf.save(update_fields=['indicadores_fiscais_confirmados'])

    def test_xml_nfe_valida_xsd(self):
        from apps.fiscal.nfe_emissao.assinatura import assinar_xml_nfe

        emp = self.nf.pedido_venda.empresa_emitente
        pfx = _criar_pfx()
        with open(pfx, 'rb') as fh:
            emp.certificado_arquivo.save('t.pfx', fh, save=True)
        emp.senha_certificado = 'test123'
        emp.save(update_fields=['senha_certificado'])

        xml_pre = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        self.assertTrue(xml_root_e_nfe(xml_pre))
        self.assertTrue(xml_contem_grupo_pag(xml_pre))
        xml = assinar_xml_nfe(xml_pre, emp, nfe_saida=self.nf).decode('utf-8')
        res = validar_xml_nfe_schema(xml, 'XML_ASSINADO')
        self.assertTrue(res['ok'], res.get('erros'))

    def test_envi_nfe_valida_xsd(self):
        from apps.fiscal.nfe_emissao.assinatura import assinar_xml_nfe

        emp = self.nf.pedido_venda.empresa_emitente
        pfx = _criar_pfx()
        with open(pfx, 'rb') as fh:
            emp.certificado_arquivo.save('t2.pfx', fh, save=True)
        emp.senha_certificado = 'test123'
        emp.save(update_fields=['senha_certificado'])

        xml_pre = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        xml = assinar_xml_nfe(xml_pre, emp, nfe_saida=self.nf).decode('utf-8')
        envi = montar_envi_nfe_xml(xml, id_lote=self.nf.pk, ind_sinc=1)
        self.assertIn('enviNFe', envi)
        self.assertIn('versao="4.00"', envi)
        self.assertIn('http://www.portalfiscal.inf.br/nfe', envi)
        res = validar_xml_nfe_schema(envi, 'ENVI_NFE')
        self.assertTrue(res['ok'], res.get('erros'))

    def test_envi_nfe_contem_nfe_uma_vez(self):
        xml = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        envi = montar_envi_nfe_xml(xml, id_lote=self.nf.pk)
        self.assertEqual(len(re.findall(r'<NFe\b', envi)), 1)

    def test_xml_tem_pag_obrigatorio(self):
        xml = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        self.assertTrue(_xml_tem_tag(xml, 'pag'))
        self.assertTrue(_xml_tem_tag(xml, 'detPag'))
        self.assertTrue(_xml_tem_tag(xml, 'tPag'))
        self.assertTrue(_xml_tem_tag(xml, 'vPag'))

    def test_xml_tem_icms_tot_completo(self):
        xml = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        for tag in ('ICMSTot', 'vBCST', 'vST', 'vNF'):
            self.assertTrue(_xml_tem_tag(xml, tag), tag)

    def test_nnf_sem_zeros_esquerda(self):
        xml = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        m = re.search(r'<(?:[\w]{1,12}:)?nNF>([^<]+)</', xml)
        self.assertIsNotNone(m)
        self.assertNotEqual(m.group(1)[0], '0')

    def test_inf_nfe_id_correto(self):
        xml = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        self.assertIn(f'NFe{self.nf.chave_acesso}', xml)

    def test_normalizar_tnfe_para_nfe(self):
        xml = gerar_xml_oficial_emissao(self.nf).decode('utf-8')
        norm = normalizar_xml_nfe(xml)
        self.assertIn('<NFe xmlns="http://www.portalfiscal.inf.br/nfe">', norm)
        self.assertNotIn('TNFe', norm)

    def test_validacao_local_bloqueia_transmissao(self):
        with patch(
            'apps.fiscal.nfe_emissao.servico.validar_emissao_completa',
            return_value={'ok': False, 'tipo': 'NFE', 'erros': [{'mensagem': 'erro xsd'}]},
        ):
            with patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao') as tx:
                with self.assertRaises(NFeEmissaoHomologacaoError):
                    emitir_nfe_homologacao(self.nf, usuario=self.user)
                tx.assert_not_called()

    def test_rejeicao_225_salva_lote_e_nfe_separados(self):
        xml_ret = """<?xml version="1.0"?>
<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <tpAmb>2</tpAmb>
  <cStat>104</cStat>
  <xMotivo>Lote processado</xMotivo>
  <protNFe versao="4.00">
    <infProt>
      <tpAmb>2</tpAmb>
      <cStat>225</cStat>
      <xMotivo>Rejeição: Falha no Schema XML do lote de NFe</xMotivo>
    </infProt>
  </protNFe>
</retEnviNFe>"""
        from apps.fiscal.nfe_emissao.aplicar_resultado import aplicar_resultado_sefaz_homologacao
        from apps.fiscal.nfe_emissao.retorno_sefaz import parse_resposta_autorizacao_pynfe

        resultado = parse_resposta_autorizacao_pynfe(0, xml_ret, xml_enviado='')
        nf = aplicar_resultado_sefaz_homologacao(
            self.nf,
            resultado,
            empresa=self.nf.pedido_venda.empresa_emitente,
            xml_envio='<enviNFe/>',
        )
        self.assertEqual(nf.cstat_lote, '104')
        self.assertEqual(nf.cstat_autorizacao, '225')

    def test_retry_reutiliza_numeracao(self):
        cfg = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.nf.pedido_venda.empresa_emitente,
            ambiente='homologacao',
            serie='0',
        )
        proximo_antes = cfg.proximo_numero
        serie = self.nf.serie_nfe
        numero = self.nf.numero_nfe
        chave = self.nf.chave_acesso

        with patch(
            'apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao',
            side_effect=Exception('mock'),
        ):
            try:
                emitir_nfe_homologacao(self.nf, usuario=self.user)
            except Exception:
                pass

        self.nf.refresh_from_db()
        cfg.refresh_from_db()
        self.assertEqual(self.nf.serie_nfe, serie)
        self.assertEqual(self.nf.numero_nfe, numero)
        self.assertEqual(self.nf.chave_acesso, chave)
        self.assertEqual(cfg.proximo_numero, proximo_antes)

    def test_endpoint_validar_xml_schema(self):
        res = self.client.post(f'/api/nf-saidas/{self.nf.pk}/validar-xml-schema/')
        self.assertIn(res.status_code, (200, 422))
        self.assertIn('ok', res.json())

    def test_endpoint_download_xml_nfe(self):
        res = self.client.get(f'/api/nf-saidas/{self.nf.pk}/xml-nfe/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<NFe', res.content)
