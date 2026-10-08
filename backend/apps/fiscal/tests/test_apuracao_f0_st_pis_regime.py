"""F0 — ICMS-ST segregado + crédito PIS/COFINS condicionado ao regime."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cadastros.models import Empresa
from apps.fiscal.models import ItemNFeEntradaHistoricaImportada, NFeEntradaHistoricaImportada
from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal, _saldo_gerencial, AcumuloLado
from apps.fiscal.services.imposto_item_xml import extrair_tributos_item


def _imposto_entrada_st_pis_credito() -> dict:
    return {
        'ICMS': {
            'ICMS10': {
                'CST': '10',
                'vBC': '100.00',
                'pICMS': '18.00',
                'vICMS': '18.00',
                'vBCST': '200.00',
                'pICMSST': '18.00',
                'vICMSST': '36.00',
                'vFCPST': '2.00',
            }
        },
        'ICMSUFDest': {
            'vBCUFDest': '100.00',
            'vICMSUFDest': '4.00',
            'vICMSUFRemet': '1.00',
            'vFCPUFDest': '0.50',
        },
        'PIS': {'PISAliq': {'CST': '50', 'vBC': '100.00', 'pPIS': '1.65', 'vPIS': '1.65'}},
        'COFINS': {'COFINSAliq': {'CST': '50', 'vBC': '100.00', 'pCOFINS': '7.60', 'vCOFINS': '7.60'}},
    }


class ExtracaoStDifalTest(TestCase):
    def test_extrai_st_e_difal_do_xml(self) -> None:
        trib = extrair_tributos_item({}, _imposto_entrada_st_pis_credito())
        self.assertEqual(trib['valor_icms'], Decimal('18.00'))
        self.assertEqual(trib['base_icms_st'], Decimal('200.00'))
        self.assertEqual(trib['valor_icms_st'], Decimal('36.00'))
        self.assertEqual(trib['valor_fcp_st'], Decimal('2.00'))
        self.assertEqual(trib['valor_icms_uf_dest'], Decimal('4.00'))
        self.assertEqual(trib['cst_pis'], '50')


class SaldoNaoCreditaIcmsStTest(TestCase):
    def test_st_nao_reduz_saldo_icms_proprio(self) -> None:
        e = AcumuloLado(valor_icms=Decimal('18'), valor_icms_st=Decimal('36'), valor_fcp_st=Decimal('2'))
        s = AcumuloLado(valor_icms=Decimal('50'), valor_icms_st=Decimal('10'))
        saldo = _saldo_gerencial(e, s)
        # ICMS próprio: 50 - 18 = 32 (ST não entra)
        self.assertAlmostEqual(saldo['valor_icms'], 32.0, places=2)
        self.assertAlmostEqual(saldo['icms_st_debito_entrada'], 36.0, places=2)
        self.assertAlmostEqual(saldo['icms_st_debito_saida'], 10.0, places=2)
        self.assertIn('débito próprio', saldo['observacao_icms_st'].lower())


class ApuracaoRegimePisCreditoTest(TestCase):
    def _criar_nf_entrada(self, empresa: Empresa | None) -> NFeEntradaHistoricaImportada:
        dh = timezone.make_aware(datetime(2026, 3, 10, 10, 0, 0))
        kwargs: dict = {
            'chave_acesso': '35260311111111111111550010000000011000000010',
            'numero': '1',
            'serie': '1',
            'modelo': '55',
            'dh_emissao': dh,
            'tp_amb': '1',
            'cstat': '100',
            'valor_total_nf': Decimal('150.00'),
            'valor_produtos': Decimal('100.00'),
        }
        if empresa is not None:
            kwargs['empresa_destinataria'] = empresa
        nf = NFeEntradaHistoricaImportada.objects.create(**kwargs)
        ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '1403', 'NCM': '84818099', 'vProd': '100.00'},
            imposto_json=_imposto_entrada_st_pis_credito(),
        )
        return nf

    def test_lucro_real_libera_credito_e_acumula_st(self) -> None:
        emp = Empresa.objects.create(
            razao_social='Nexus Lucro Real',
            cnpj='11.111.111/0001-11',
            ie='123',
            regime_tributario='Lucro Real',
        )
        self._criar_nf_entrada(emp)
        pl = build_apuracao_fiscal(
            {
                'empresa_id': str(emp.id),
                'data_inicio': '2026-03-01',
                'data_fim': '2026-03-31',
                'tipo': 'ENTRADA',
                'fonte': 'HISTORICOS',
            }
        )
        self.assertEqual(pl['regime_tributario']['classificado'], 'LUCRO_REAL')
        self.assertTrue(pl['regime_tributario']['permite_credito_pis_cofins'])
        self.assertAlmostEqual(pl['cards']['pis_credito'], 1.65, places=2)
        self.assertAlmostEqual(pl['cards']['cofins_credito'], 7.60, places=2)
        self.assertAlmostEqual(pl['cards']['icms_st_debito_entrada'], 36.0, places=2)
        self.assertAlmostEqual(pl['resumo']['entrada']['valor_icms_st'], 36.0, places=2)
        self.assertAlmostEqual(pl['resumo']['entrada']['valor_icms'], 18.0, places=2)
        # ST não neteia no saldo como crédito (entrada só → ICMS próprio negativo, ST separado)
        saldo = pl['resumo']['saldo_gerencial_saida_menos_entrada']
        self.assertAlmostEqual(saldo['valor_icms'], -18.0, places=2)
        self.assertAlmostEqual(saldo['icms_st_debito_entrada'], 36.0, places=2)

    def test_lucro_presumido_bloqueia_credito(self) -> None:
        emp = Empresa.objects.create(
            razao_social='Nexus Presumido',
            cnpj='22.222.222/0001-22',
            ie='456',
            regime_tributario='Lucro Presumido',
        )
        self._criar_nf_entrada(emp)
        pl = build_apuracao_fiscal(
            {
                'empresa_id': str(emp.id),
                'data_inicio': '2026-03-01',
                'data_fim': '2026-03-31',
                'tipo': 'ENTRADA',
                'fonte': 'HISTORICOS',
            }
        )
        self.assertEqual(pl['regime_tributario']['classificado'], 'LUCRO_PRESUMIDO')
        self.assertFalse(pl['regime_tributario']['permite_credito_pis_cofins'])
        self.assertAlmostEqual(pl['cards']['pis_credito'], 0.0, places=2)
        self.assertAlmostEqual(pl['cards']['cofins_credito'], 0.0, places=2)
        # Valor destacado no XML continua no acumulo bruto
        self.assertAlmostEqual(pl['resumo']['entrada']['valor_pis'], 1.65, places=2)
        self.assertGreaterEqual(pl['cards']['credito_pis_cofins_bloqueado_regime_itens'], 1)
        codigos = {a['codigo'] for a in pl['alertas']}
        self.assertIn('CREDITO_PIS_COFINS_BLOQUEADO_REGIME', codigos)
