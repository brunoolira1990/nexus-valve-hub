"""Regressão cStat 798 — vFCPUFDest total deve igualar soma dos itens no XML."""

from __future__ import annotations

import re
import unittest
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.fiscal.nfe_difal_calculo import (
    agregar_totais_difal,
    difal_emitido_no_item,
    valores_difal_item_xml,
)
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_saida_xml_nfelib import (
    _enriquecer_totais_impostos,
    montar_tnfe_oficial,
    serializar_tnfe,
)
from apps.fiscal.tests.test_nfe_reforma_xml_401369 import _dados_xml_base


def _linha_com_difal(
    *,
    n_item: str = '1',
    v_prod: str = '1000.00',
    difal: dict,
) -> dict:
    base = {
        'n_item': n_item,
        'item_id': int(n_item),
        'c_prod': f'P{n_item}',
        'x_prod': f'Produto {n_item}',
        'ncm': '73079100',
        'cfop': '6102',
        'u_com': 'UN',
        'q_com': '1',
        'v_un_com': v_prod,
        'v_prod': v_prod,
        'snapshot_fiscal': {
            'ncm': '73079100',
            'cfop': '6102',
            'cst_icms': '00',
            'aliquota_icms': '12',
            'base_icms': v_prod,
            'valor_icms': '120.00',
            'cst_pis': '01',
            'valor_pis': '6.50',
            'cst_cofins': '01',
            'valor_cofins': '30.00',
            'difal': difal,
        },
    }
    return base


def _icms_uf_dest(det) -> object | None:
    icms = det.imposto.ICMS
    return getattr(icms, 'ICMSUFDest', None) or getattr(icms, 'Icmsufdest', None)


def _somar_vfcp_itens_tnfe(tnfe) -> Decimal:
    total = Decimal('0')
    for det in tnfe.infNFe.det:
        ufdest = _icms_uf_dest(det)
        if ufdest is not None and ufdest.vFCPUFDest is not None:
            total += Decimal(str(ufdest.vFCPUFDest))
    return total

DIFAL_SETTINGS = {
    'REFORMA_TRIBUTARIA_NFE_ENABLED': False,
}


class DifalCalculoCstat798Tests(TestCase):
    def test_emitido_quando_so_fcp_sem_flag_aplicavel(self):
        difal = {
            'v_bc_uf_dest': '1000.00',
            'p_icms_uf_dest': '18.00',
            'p_icms_inter': '12.00',
            'p_icms_inter_part': '100.00',
            'p_fcp_uf_dest': '2.00',
            'v_fcp_uf_dest': '20.00',
            'v_icms_uf_dest': '0.00',
            'v_icms_uf_remet': '0.00',
        }
        self.assertTrue(difal_emitido_no_item(difal))

    def test_agregar_usa_mesma_regra_de_emissao_por_item(self):
        itens = [
            {
                'v_fcp_uf_dest': '50.00',
                'p_fcp_uf_dest': '2.00',
                'v_icms_uf_dest': '100.00',
                'v_icms_uf_remet': '0.00',
            },
            {
                'v_fcp_uf_dest': '96.77',
                'p_fcp_uf_dest': '2.00',
                'v_icms_uf_dest': '1881.36',
                'v_icms_uf_remet': '0.00',
            },
        ]
        totais = agregar_totais_difal(itens)
        self.assertEqual(totais['v_fcp_uf_dest'], '146.77')
        self.assertEqual(totais['v_icms_uf_dest'], '1981.36')

    def test_agregar_ignora_fcp_quando_p_e_valor_zero(self):
        difal = {
            'aplicavel': True,
            'v_fcp_uf_dest': '0.00',
            'p_fcp_uf_dest': '0.00',
            'v_icms_uf_dest': '50.00',
            'v_icms_uf_remet': '0.00',
        }
        valores = valores_difal_item_xml(difal)
        assert valores is not None
        self.assertEqual(valores['v_fcp_uf_dest'], Decimal('0'))
        totais = agregar_totais_difal([difal])
        self.assertNotIn('v_fcp_uf_dest', totais)
        self.assertEqual(totais['v_icms_uf_dest'], '50.00')


@override_settings(**DIFAL_SETTINGS)
@unittest.skipUnless(nfelib_disponivel(), 'nfelib não instalado')
class DifalXmlTotaisCstat798Tests(TestCase):
    def test_item_com_fcp_sem_icms_dest_entra_no_xml_e_total_bate(self):
        dados = _dados_xml_base()
        dados['itens'] = [
            _linha_com_difal(
                difal={
                    'v_bc_uf_dest': '5000.00',
                    'v_bc_fcp_uf_dest': '5000.00',
                    'p_fcp_uf_dest': '2.00',
                    'p_icms_uf_dest': '18.00',
                    'p_icms_inter': '12.00',
                    'p_icms_inter_part': '100.00',
                    'v_fcp_uf_dest': '100.00',
                    'v_icms_uf_dest': '0.00',
                    'v_icms_uf_remet': '0.00',
                },
            ),
            _linha_com_difal(
                n_item='2',
                v_prod='4838.50',
                difal={
                    'v_bc_uf_dest': '4838.50',
                    'v_bc_fcp_uf_dest': '4838.50',
                    'p_fcp_uf_dest': '2.00',
                    'p_icms_uf_dest': '18.00',
                    'p_icms_inter': '12.00',
                    'p_icms_inter_part': '100.00',
                    'v_fcp_uf_dest': '46.77',
                    'v_icms_uf_dest': '290.31',
                    'v_icms_uf_remet': '0.00',
                },
            ),
        ]
        _enriquecer_totais_impostos(dados)
        tnfe = montar_tnfe_oficial(dados)
        soma_itens = _somar_vfcp_itens_tnfe(tnfe)
        total_icms = Decimal(str(tnfe.infNFe.total.ICMSTot.vFCPUFDest or 0))
        self.assertEqual(soma_itens, Decimal('146.77'))
        self.assertEqual(total_icms, soma_itens)
        self.assertEqual(len(tnfe.infNFe.det), 2)
        for det in tnfe.infNFe.det:
            self.assertIsNotNone(_icms_uf_dest(det))

        xml = serializar_tnfe(tnfe, pretty=False)
        tags_fcp = re.findall(
            r'<(?:[\w]{1,12}:)?vFCPUFDest>([^<]+)</',
            xml,
            re.IGNORECASE,
        )
        self.assertEqual(len(tags_fcp), 3)
        self.assertEqual(sum(Decimal(v) for v in tags_fcp[:-1]), Decimal(tags_fcp[-1]))
