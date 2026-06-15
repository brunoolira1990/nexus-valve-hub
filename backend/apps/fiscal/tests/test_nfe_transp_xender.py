"""Testes — montagem transporta/xEnder da transportadora no XML NF-e."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.fiscal.nfe_transp_bindings import (
    aplicar_transp_nfelib,
    montar_xender_transportadora,
    normalizar_xender_transportadora_xml,
)


class NfeTranspXenderTests(SimpleTestCase):
    def test_montar_xender_sem_bairro_nem_virgula_final(self):
        ender = montar_xender_transportadora('AVENIDA PAPA JOAO PAULO I', '6211')
        self.assertEqual(ender, 'AVENIDA PAPA JOAO PAULO I 6211')
        self.assertNotIn(',', ender)
        self.assertFalse(ender.endswith(' '))
        self.assertNotIn('RESIDENCIAL', ender)

    def test_montar_xender_inclui_complemento_quando_cabe(self):
        ender = montar_xender_transportadora('RUA TESTE', '100', 'SALA 2')
        self.assertEqual(ender, 'RUA TESTE 100 SALA 2')

    def test_normalizar_remove_virgula_e_espaco_final(self):
        self.assertEqual(
            normalizar_xender_transportadora_xml(
                'AVENIDA PAPA JOAO PAULO I 6211, RESIDENCIAL PARQUE CUMBICA, ',
            ),
            'AVENIDA PAPA JOAO PAULO I 6211, RESIDENCIAL PARQUE CUMBICA',
        )

    def test_aplicar_transp_nfelib_xender_valido(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(
            inf,
            nfe,
            {
                'mod_frete': '0',
                'transportadora_nome': 'TRANSPORTADORA TESTE LTDA',
                'transportadora_cnpj': '32241095000121',
                'transportadora_ender': montar_xender_transportadora(
                    'AVENIDA PAPA JOAO PAULO I',
                    '6211',
                ),
                'transportadora_mun': 'GUARULHOS',
                'transportadora_uf': 'SP',
            },
        )
        self.assertEqual(inf.transp.transporta.xEnder, 'AVENIDA PAPA JOAO PAULO I 6211')
