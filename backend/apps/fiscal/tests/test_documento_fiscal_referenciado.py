"""Texto de NF-e referenciada nas Informações Complementares."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from django.test import SimpleTestCase

from apps.fiscal.nfe_integracao.documento_fiscal_referenciado import (
    anexar_referencias_ao_inf_cpl,
    chaves_ref_nfe_do_ide,
    formatar_chave_acesso_nfe,
    montar_inf_cpl_entrada_com_referencia,
    texto_documento_fiscal_referenciado,
)

CHAVE = '35260503999102000150550010000003531216446330'


class DocumentoFiscalReferenciadoTests(SimpleTestCase):
    def test_formata_chave_em_grupos_de_4(self):
        self.assertEqual(
            formatar_chave_acesso_nfe(CHAVE),
            '3526 0503 9991 0200 0150 5500 1000 0003 5312 1644 6330',
        )

    def test_texto_padrao(self):
        txt = texto_documento_fiscal_referenciado(CHAVE)
        self.assertTrue(txt.startswith('DOCUMENTO FISCAL REFERENCIADO:'))
        self.assertIn(CHAVE[:4], txt)

    def test_monta_inf_cpl_entrada(self):
        txt = montar_inf_cpl_entrada_com_referencia(chave_nfe_referenciada=CHAVE)
        self.assertIn('DOCUMENTO FISCAL REFERENCIADO', txt)
        self.assertIn(CHAVE.replace(' ', ''), txt.replace(' ', ''))

    def test_nao_duplica_chave_ja_presente(self):
        base = texto_documento_fiscal_referenciado(CHAVE)
        self.assertEqual(anexar_referencias_ao_inf_cpl(base, [CHAVE]), base)

    def test_extrai_refnfe_do_ide(self):
        ns = 'http://www.portalfiscal.inf.br/nfe'
        ide = Element(f'{{{ns}}}ide')
        nfref = Element(f'{{{ns}}}NFref')
        ref = Element(f'{{{ns}}}refNFe')
        ref.text = CHAVE
        nfref.append(ref)
        ide.append(nfref)
        self.assertEqual(chaves_ref_nfe_do_ide(ide), [CHAVE])
