"""CBS/IBS (Reforma): extração a partir de JSON fiel ao XML (NF-e e CT-e)."""
from __future__ import annotations

from decimal import Decimal
from unittest import TestCase

from apps.fiscal.services.reforma_tributaria import (
    TotaisReformaTributaria,
    extrair_ibscbstot_totais_json,
    merge_totais_reforma,
    processar_reforma_cte_imposto,
    processar_reforma_nfe_historica,
)


class IbscbsReformaExtracaoTest(TestCase):
    def test_nfe_saida_cst_e_ibscbstot_zerados(self) -> None:
        totais = {
            'IBSCBSTot': {
                'vBCIBSCBS': '0.00',
                'gIBS': {'gIBSUF': {'vIBSUF': '0.00'}, 'gIBSMun': {'vIBSMun': '0.00'}, 'vIBS': '0.00'},
                'gCBS': {'vCBS': '0.00'},
            }
        }
        impostos = [{'IBSCBS': {'CST': '410', 'cClassTrib': '410999'}}]
        doc_tot, alertas, stats = processar_reforma_nfe_historica(totais, {}, impostos)
        self.assertEqual(stats['itens_com_tags_ibscbs'], 1)
        self.assertEqual(stats['itens_com_valores_ibscbs'], 0)
        self.assertEqual(stats['nota_com_ibscbstot'], 1)
        self.assertEqual(doc_tot['valor_cbs'], Decimal('0'))
        self.assertEqual(doc_tot['valor_ibs_uf'], Decimal('0'))
        self.assertTrue(any('zerados' in a for a in alertas))

    def test_nfe_entrada_dois_itens_soma(self) -> None:
        item = {
            'IBSCBS': {
                'CST': '000',
                'cClassTrib': '000001',
                'gIBSCBS': {
                    'vBC': '254.09',
                    'gIBSUF': {'pIBSUF': '0.1000', 'vIBSUF': '0.25'},
                    'gIBSMun': {'pIBSMun': '0.0000', 'vIBSMun': '0.00'},
                    'vIBS': '0.25',
                    'gCBS': {'pCBS': '0.9000', 'vCBS': '2.29'},
                },
            }
        }
        doc_tot, _a, stats = processar_reforma_nfe_historica({}, {}, [item, item])
        self.assertEqual(stats['itens_com_tags_ibscbs'], 2)
        self.assertEqual(stats['itens_com_valores_ibscbs'], 2)
        self.assertEqual(doc_tot['base_cbs'], Decimal('508.18'))
        self.assertEqual(doc_tot['valor_ibs_uf'], Decimal('0.50'))
        self.assertEqual(doc_tot['valor_ibs_municipio'], Decimal('0'))
        self.assertEqual(doc_tot['valor_cbs'], Decimal('4.58'))

    def test_cte_imp_ibscbs_valores(self) -> None:
        imp = {
            'IBSCBS': {
                'CST': '000',
                'cClassTrib': '000001',
                'gIBSCBS': {
                    'vBC': '742.12',
                    'gIBSUF': {'pIBSUF': '0.10', 'vIBSUF': '0.74'},
                    'gIBSMun': {'pIBSMun': '0.00', 'vIBSMun': '0.00'},
                    'vIBS': '0.74',
                    'gCBS': {'pCBS': '0.90', 'vCBS': '6.68'},
                },
            }
        }
        ctot, _al, st = processar_reforma_cte_imposto(imp)
        self.assertEqual(st['cte_com_tags_ibscbs'], 1)
        self.assertEqual(st['cte_com_valores_ibscbs'], 1)
        self.assertEqual(ctot['base_cbs'], Decimal('742.12'))
        self.assertEqual(ctot['valor_ibs_uf'], Decimal('0.74'))
        self.assertEqual(ctot['valor_cbs'], Decimal('6.68'))

    def test_ibscbstot_em_wrapper_total(self) -> None:
        totais_wrapped = {
            'total': {
                'ICMSTot': {'vNF': '710.34'},
                'IBSCBSTot': {
                    'vBCIBSCBS': '508.18',
                    'gIBS': {
                        'gIBSUF': {'vIBSUF': '0.50'},
                        'gIBSMun': {'vIBSMun': '0.00'},
                        'vIBS': '0.50',
                    },
                    'gCBS': {'vCBS': '4.58'},
                },
            }
        }
        j = extrair_ibscbstot_totais_json(totais_wrapped)
        self.assertIsNotNone(j)
        assert j is not None
        self.assertAlmostEqual(j['cbs_valor'], 4.58, places=2)

    def test_processar_com_imposto_json_string(self) -> None:
        import json

        item = {
            'IBSCBS': {
                'CST': '000',
                'cClassTrib': '000001',
                'gIBSCBS': {
                    'vBC': '254.09',
                    'gCBS': {'vCBS': '2.29'},
                    'gIBSUF': {'vIBSUF': '0.25'},
                    'gIBSMun': {'vIBSMun': '0.00'},
                    'vIBS': '0.25',
                },
            }
        }
        imp_str = json.dumps(item)
        doc_tot, _a, stats = processar_reforma_nfe_historica({}, {}, [imp_str])
        self.assertEqual(stats['itens_com_valores_ibscbs'], 1)
        self.assertEqual(doc_tot['valor_cbs'], Decimal('2.29'))

    def test_merge_totais_acumula_ibs_municipio(self) -> None:
        ac = TotaisReformaTributaria()
        merge_totais_reforma(
            ac,
            {
                'valor_cbs': Decimal('1'),
                'valor_ibs_uf': Decimal('2'),
                'valor_ibs_municipio': Decimal('3'),
                'valor_is': Decimal('4'),
                'base_ibs': Decimal('10'),
                'base_cbs': Decimal('10'),
            },
        )
        self.assertEqual(ac.valor_cbs, Decimal('1'))
        self.assertEqual(ac.valor_ibs_uf, Decimal('2'))
        self.assertEqual(ac.valor_ibs_municipio, Decimal('3'))
