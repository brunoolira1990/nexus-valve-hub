"""Testes — serialização legível de erros XSD emissão NF-e."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.nfe_emissao.xsd_erros import (
    aplicar_erros_validacao_no_payload,
    formatar_erro_xsd_legivel,
    preparar_erros_resposta_emissao,
    serializar_lista_erros_xsd,
)


class XsdErrosSerializacaoTests(SimpleTestCase):
    def test_formatar_erro_xsd_com_tag_e_contexto(self):
        texto = formatar_erro_xsd_legivel(
            {
                'contexto': 'XML_ASSINADO',
                'elemento': '/NFe/{http://www.portalfiscal.inf.br/nfe}infNFe/{http://www.portalfiscal.inf.br/nfe}ide/{http://www.portalfiscal.inf.br/nfe}tpAmb',
                'mensagem': "Element 'tpAmb': '2' is not a valid value of the atomic type 'TAmb'.",
                'linha': 12,
                'coluna': 9,
            },
        )
        self.assertIn('XML assinado', texto)
        self.assertIn('Tag tpAmb', texto)
        self.assertIn('TAmb', texto)
        self.assertIn('linha 12', texto)

    def test_serializar_lista_converte_dict_em_string(self):
        erros_txt, erros_xsd = serializar_lista_erros_xsd(
            [
                {
                    'contexto': 'XML_ASSINADO',
                    'mensagem': 'Valor inválido no campo CST.',
                    'linha': 40,
                },
            ],
            contexto_padrao='XML_ASSINADO',
        )
        self.assertEqual(len(erros_txt), 1)
        self.assertIsInstance(erros_txt[0], str)
        self.assertIn('Valor inválido', erros_txt[0])
        self.assertEqual(len(erros_xsd), 1)
        self.assertEqual(erros_xsd[0]['contexto'], 'XML_ASSINADO')

    def test_preparar_resposta_emissao_marca_sefaz_nao_transmitida(self):
        prep = preparar_erros_resposta_emissao(
            [
                {
                    'contexto': 'XML_ASSINADO',
                    'elemento': '/NFe/{http://www.portalfiscal.inf.br/nfe}infNFe/{http://www.portalfiscal.inf.br/nfe}det/{http://www.portalfiscal.inf.br/nfe}imposto',
                    'mensagem': "Missing child element(s). Expected is ( {http://www.portalfiscal.inf.br/nfe}ICMS ).",
                    'linha': 88,
                    'coluna': 0,
                },
            ],
            validacao_xsd={'ok': False, 'tipo': 'XML_ASSINADO'},
            mensagem='Falha na validação XSD local antes da transmissão produção.',
        )
        self.assertFalse(prep['sefaz_transmitida'])
        self.assertTrue(all(isinstance(e, str) for e in prep['erros']))
        self.assertIn('erros_xsd', prep)
        self.assertIn('Missing child element', prep['erros'][0])

    def test_aplicar_erros_validacao_no_payload_api(self):
        payload = {'ok': False, 'mensagem': 'Falha XSD', 'erros': [{}]}
        det = {
            'validacao_xsd': {'ok': False, 'tipo': 'XML_ASSINADO'},
            'erros': [
                {
                    'contexto': 'XML_ASSINADO',
                    'mensagem': 'Campo inválido.',
                    'linha': 1,
                },
            ],
        }
        aplicar_erros_validacao_no_payload(payload, det, mensagem='Falha XSD')
        self.assertFalse(payload['sefaz_transmitida'])
        self.assertIsInstance(payload['erros'][0], str)
        self.assertIn('Campo inválido', payload['erros'][0])
