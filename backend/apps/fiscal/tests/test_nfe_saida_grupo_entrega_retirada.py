"""Ordem do grupo <retirada>/<entrega> no XML da NF-e (leiaute 4.00).

Sequencia de <infNFe> no XSD: ... dest, retirada, entrega, autXML, det ...
(TLocal: CNPJ|CPF, xNome, xLgr, nro, xCpl, xBairro, cMun, xMun, UF, CEP).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from lxml import etree

from apps.fiscal.nfe_emissao.xml_oficial import _preparar_dados_emissao, montar_tnfe_emissao
from apps.fiscal.nfe_emissao.xml_serializacao import serializar_tnfe_nfe
from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe
from apps.fiscal.nfe_saida_preview import _xml_preview_string, gerar_dados_preview_nfe_saida
from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import _pedido_nf

NS_NFE = 'http://www.portalfiscal.inf.br/nfe'

CHAVE_44 = '35' + '1' * 41 + '0'


def _chave() -> ChaveAcessoNFe:
    return ChaveAcessoNFe(
        chave_43=CHAVE_44[:43],
        digito_verificador=CHAVE_44[-1],
        chave_44=CHAVE_44,
        inf_nfe_id=f'NFe{CHAVE_44}',
    )


def _local(tag: str) -> str:
    return etree.QName(tag).localname


def _inf_children(xml: str | bytes) -> list[etree._Element]:
    root = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
    inf = root.find(f'.//{{{NS_NFE}}}infNFe')
    assert inf is not None, 'infNFe ausente no XML'
    return list(inf)


def _parse_preview(xml: str) -> list[etree._Element]:
    # _xml_preview_string emite a declaracao XML duas vezes (minidom.toxml);
    # descartamos o cabecalho/commentario para conseguir transformar em arvore.
    body = xml.split('-->\n', 1)[1] if '-->\n' in xml else xml
    root = etree.fromstring(body.encode('utf-8'))
    inf = root.find(f'.//{{{NS_NFE}}}infNFe')
    assert inf is not None, 'infNFe ausente no XML de preview'
    return list(inf)


class NFeSaidaGrupoEntregaRetiradaOrdemTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ordem_tlocal', 'ordem@test.com', 'x')
        self.pedido, self.item, self.nf = _pedido_nf()
        self.nf.ind_final = '1'
        self.nf.ind_pres = '1'
        self.nf.indicadores_fiscais_confirmados = True
        self.nf.numero_nfe = '1'
        self.nf.serie_nfe = '1'
        self.nf.codigo_numerico = '12345678'
        self.nf.save(
            update_fields=[
                'ind_final',
                'ind_pres',
                'indicadores_fiscais_confirmados',
                'numero_nfe',
                'serie_nfe',
                'codigo_numerico',
            ],
        )
        self.nf.retirada_cnpj = '12345678000199'
        self.nf.retirada_xNome = 'Retirada Teste'
        self.nf.retirada_xLgr = 'Rua Retirada'
        self.nf.retirada_nro = '10'
        self.nf.retirada_xBairro = 'Centro'
        self.nf.retirada_cMun = '3550308'
        self.nf.retirada_xMun = 'Sao Paulo'
        self.nf.retirada_UF = 'SP'
        self.nf.retirada_CEP = '01001000'
        self.nf.entrega_cpf = '12345678901'
        self.nf.entrega_xNome = 'Entrega Teste'
        self.nf.entrega_xLgr = 'Rua Entrega'
        self.nf.entrega_nro = '20'
        self.nf.entrega_xBairro = 'Centro'
        self.nf.entrega_cMun = '3550308'
        self.nf.entrega_xMun = 'Sao Paulo'
        self.nf.entrega_UF = 'SP'
        self.nf.entrega_CEP = '01001000'
        self.nf.save()

    def _xml_oficial(self) -> str:
        dados = _preparar_dados_emissao(self.nf)
        tnfe = montar_tnfe_emissao(
            dados,
            nfe_saida=self.nf,
            chave=_chave(),
            serie=self.nf.serie_nfe,
            nnf=self.nf.numero_nfe,
            codigo_numerico=self.nf.codigo_numerico,
        )
        return serializar_tnfe_nfe(tnfe)

    def test_xml_oficial_ordem_dest_retirada_entrega_det(self):
        xml = self._xml_oficial()
        filhos = _inf_children(xml)
        tags = [_local(el.tag) for el in filhos]

        self.assertLess(tags.index('dest'), tags.index('retirada'))
        self.assertLess(tags.index('retirada'), tags.index('entrega'))
        self.assertLess(tags.index('entrega'), tags.index('det'))

    def test_xml_oficial_tlocal_cnpj_cpf_primeiro_filho(self):
        xml = self._xml_oficial()
        filhos = _inf_children(xml)
        por_tag = {_local(el.tag): el for el in filhos}

        retirada = [_local(el.tag) for el in por_tag['retirada']]
        self.assertEqual(retirada[0], 'CNPJ')
        self.assertEqual(por_tag['retirada'][0].text, '12345678000199')
        self.assertLess(retirada.index('cMun'), retirada.index('xMun'))
        self.assertLess(retirada.index('xMun'), retirada.index('UF'))
        self.assertLess(retirada.index('UF'), retirada.index('CEP'))

        entrega = [_local(el.tag) for el in por_tag['entrega']]
        self.assertEqual(entrega[0], 'CPF')
        self.assertEqual(por_tag['entrega'][0].text, '12345678901')
        self.assertLess(entrega.index('cMun'), entrega.index('xMun'))

    def test_preview_ordem_dest_retirada_entrega_det(self):
        dados = gerar_dados_preview_nfe_saida(self.nf, incluir_validacao_emissao=False)
        xml = _xml_preview_string(dados)
        filhos = _parse_preview(xml)
        tags = [_local(el.tag) for el in filhos]

        self.assertLess(tags.index('dest'), tags.index('retirada'))
        self.assertLess(tags.index('retirada'), tags.index('entrega'))
        self.assertLess(tags.index('entrega'), tags.index('det'))

    def test_preview_tlocal_cnpj_cpf_primeiro_filho(self):
        dados = gerar_dados_preview_nfe_saida(self.nf, incluir_validacao_emissao=False)
        xml = _xml_preview_string(dados)
        filhos = _parse_preview(xml)
        por_tag = {_local(el.tag): el for el in filhos}

        retirada = [_local(el.tag) for el in por_tag['retirada']]
        self.assertEqual(retirada[0], 'CNPJ')
        self.assertLess(retirada.index('cMun'), retirada.index('xMun'))

        entrega = [_local(el.tag) for el in por_tag['entrega']]
        self.assertEqual(entrega[0], 'CPF')
        self.assertLess(entrega.index('cMun'), entrega.index('xMun'))
