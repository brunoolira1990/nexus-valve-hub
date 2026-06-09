"""Apuração fiscal: Reforma (CBS/IBS) a partir de NF-e entrada histórica importada."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.fiscal.models import ItemNFeEntradaHistoricaImportada, NFeEntradaHistoricaImportada
from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal


class ApuracaoReformaEntradaHistoricaTest(TestCase):
    def test_nf_entrada_hist_contribui_cards_e_diagnostico(self) -> None:
        dh = timezone.make_aware(datetime(2026, 1, 20, 14, 35, 6))
        totais = {
            'IBSCBSTot': {
                'vBCIBSCBS': '508.18',
                'gIBS': {
                    'gIBSUF': {'vIBSUF': '0.50'},
                    'gIBSMun': {'vIBSMun': '0.00'},
                    'vIBS': '0.50',
                },
                'gCBS': {'vCBS': '4.58'},
            }
        }
        item_ibscbs = {
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
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso='35260101645083000139550010000274491851390322',
            numero='27449',
            serie='1',
            modelo='55',
            dh_emissao=dh,
            tp_amb='1',
            cstat='100',
            totais_json=totais,
            valor_total_nf=Decimal('710.34'),
        )
        ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '5401', 'NCM': '85045090'},
            imposto_json=item_ibscbs,
        )
        ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=2,
            prod_json={'CFOP': '5401', 'NCM': '85045090'},
            imposto_json=item_ibscbs,
        )

        pl = build_apuracao_fiscal(
            {
                'data_inicio': '2026-01-01',
                'data_fim': '2026-01-31',
                'tipo': 'ENTRADA',
                'fonte': 'HISTORICOS',
            }
        )
        self.assertAlmostEqual(pl['cards']['cbs'], 4.58, places=2)
        self.assertAlmostEqual(pl['cards']['ibs'], 0.50, places=2)
        self.assertAlmostEqual(pl['cards']['base_cbs_entrada'], 508.18, places=2)
        self.assertAlmostEqual(pl['cards']['cbs_entrada'], 4.58, places=2)
        self.assertAlmostEqual(pl['cards']['ibs_total_entrada'], 0.50, places=2)

        dr = pl['diagnostico_reforma']
        self.assertEqual(dr['candidatas_entrada_historica'], 1)
        self.assertAlmostEqual(dr['entrada']['valor_cbs'], 4.58, places=2)
        self.assertAlmostEqual(dr['entrada']['valor_ibs_total'], 0.50, places=2)
        self.assertEqual(dr['entrada']['itens_com_tags_ibscbs'], 2)

        por = pl['reforma_tributaria']['por_documento']['entrada']
        self.assertAlmostEqual(por['valor_cbs'], 4.58, places=2)
