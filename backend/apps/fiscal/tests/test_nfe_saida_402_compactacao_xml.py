"""NF-e 4.0.2 — compactação XML (rejeição SEFAZ cStat 588)."""

from __future__ import annotations

import re
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.envi_nfe import montar_envi_nfe_compacto
from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.xml_compactacao import (
    BOM_UTF8,
    debug_xml_bytes,
    normalizar_xml_para_assinatura_nfe,
    tem_caracteres_edicao,
    validar_xml_sem_caracteres_edicao,
)
from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao
from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf


class NFe402CompactacaoXmlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username=f'compact_{uuid.uuid4().hex[:8]}',
            password='test123',
        )
        _, _, nf = _pedido_nf()
        nf.ind_final = '1'
        nf.ind_pres = '1'
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
        marcar_nfe_pronta_para_emissao(nf, usuario=cls.user)
        reservar_numeracao_nfe(nf, ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO, usuario=cls.user)
        nf.refresh_from_db()
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['indicadores_fiscais_confirmados'])
        cls.nf = nf

    def setUp(self):
        self.nf = NFeSaida.objects.get(pk=self.__class__.nf.pk)
        self.user = self.__class__.user
        self._patch_cep = patch(
            'apps.cadastros.endereco_fiscal.consultar_cep_viacep',
            return_value=None,
        )
        self._patch_cep.start()

    def tearDown(self):
        self._patch_cep.stop()

    def _xml_oficial(self) -> bytes:
        return gerar_xml_oficial_emissao(self.nf)

    def test_xml_nfe_sem_bom(self):
        xml = self._xml_oficial()
        self.assertFalse(xml.startswith(BOM_UTF8))

    def test_xml_nfe_sem_whitespace_antes_primeira_tag(self):
        xml = self._xml_oficial().decode('utf-8')
        corpo = xml.split('?>', 1)[-1]
        self.assertTrue(corpo.startswith('<'), corpo[:20])

    def test_xml_nfe_sem_quebra_entre_tags(self):
        xml = self._xml_oficial()
        corpo = xml.split(b'?>', 1)[-1]
        self.assertNotRegex(corpo, rb'>\s+[\r\n]+\s*<')

    def test_xml_nfe_sem_tab_entre_tags(self):
        xml = self._xml_oficial()
        corpo = xml.split(b'?>', 1)[-1]
        self.assertNotRegex(corpo, rb'>\s*\t+\s*<')

    def test_envi_nfe_compacto(self):
        xml = self._xml_oficial().decode('utf-8')
        envi = montar_envi_nfe_compacto(xml, id_lote=self.nf.pk)
        self.assertIn('enviNFe', envi)
        corpo = envi.split('?>', 1)[-1]
        self.assertNotRegex(corpo.encode(), rb'>\s+[\r\n]+\s*<')

    def test_validacao_detecta_quebra_entre_tags(self):
        ruim = b'<?xml version="1.0"?><a>\n</a>'
        res = validar_xml_sem_caracteres_edicao(ruim)
        self.assertFalse(res['ok'])

    def test_validacao_detecta_bom(self):
        ruim = BOM_UTF8 + b'<a/>'
        self.assertTrue(tem_caracteres_edicao(ruim))

    def test_normalizacao_preserva_texto_inf_cpl(self):
        xml_indentado = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">\n'
            '  <infNFe versao="4.00" Id="NFePREVIEW1">\n'
            '    <infAdic><infCpl>TEXTO COM  ESPACOS INTERNOS VALIDOS</infCpl></infAdic>\n'
            '  </infNFe>\n'
            '</NFe>\n'
        )
        out = normalizar_xml_para_assinatura_nfe(xml_indentado).decode('utf-8')
        self.assertIn('ESPACOS INTERNOS VALIDOS', out)
        self.assertFalse(tem_caracteres_edicao(out))

    def test_pretty_print_xsdata_gera_compacto_apos_normalizar(self):
        xml = self._xml_oficial()
        self.assertFalse(tem_caracteres_edicao(xml))

    def test_rejeicao_588_salva_lote_e_nfe_separados(self):
        from apps.fiscal.nfe_emissao.aplicar_resultado import aplicar_resultado_sefaz_homologacao
        from apps.fiscal.nfe_emissao.retorno_sefaz import parse_resposta_autorizacao_pynfe

        xml_ret = """<?xml version="1.0"?>
<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <cStat>104</cStat>
  <xMotivo>Lote processado</xMotivo>
  <protNFe versao="4.00">
    <infProt>
      <cStat>588</cStat>
      <xMotivo>Rejeição: Não é permitida a presença de caracteres de edição</xMotivo>
    </infProt>
  </protNFe>
</retEnviNFe>"""
        resultado = parse_resposta_autorizacao_pynfe(0, xml_ret, xml_enviado='')
        nf = aplicar_resultado_sefaz_homologacao(
            self.nf,
            resultado,
            empresa=self.nf.pedido_venda.empresa_emitente,
            xml_envio='<enviNFe/>',
        )
        self.assertEqual(nf.cstat_lote, '104')
        self.assertEqual(nf.cstat_autorizacao, '588')

    def test_retry_reutiliza_numeracao(self):
        cfg_antes = self.nf.serie_nfe, self.nf.numero_nfe, self.nf.chave_acesso
        with patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []}):
            with patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao', side_effect=Exception('mock')):
                from apps.fiscal.nfe_emissao.servico import NFeEmissaoHomologacaoError, emitir_nfe_homologacao

                try:
                    emitir_nfe_homologacao(self.nf, usuario=self.user)
                except (NFeEmissaoHomologacaoError, Exception):
                    pass
        self.nf.refresh_from_db()
        self.assertEqual((self.nf.serie_nfe, self.nf.numero_nfe, self.nf.chave_acesso), cfg_antes)

    def test_debug_xml_bytes(self):
        diag = debug_xml_bytes(self._xml_oficial())
        self.assertIn('tamanho', diag)
        self.assertFalse(diag['contem_bom'])
