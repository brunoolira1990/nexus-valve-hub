"""ERP 4.0.10.1 — organização DF-e e exclusão de homologação da apuração."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cadastros.models import Cliente
from apps.fiscal.dfe_classificacao import (
    pode_alimentar_precificacao,
    pode_entrar_apuracao,
    pode_gerar_efeito_operacional,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaidaHistoricaImportada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from apps.fiscal.services.apuracao_fiscal import build_apuracao_fiscal


def _dh(y: int, m: int, d: int) -> datetime:
    return timezone.make_aware(datetime(y, m, d, 12, 0, 0))


def _item_icms() -> dict:
    return {
        'ICMS': {'ICMS00': {'CST': '00', 'vBC': '100.00', 'pICMS': '18.00', 'vICMS': '18.00'}},
        'PIS': {'PISAliq': {'CST': '01', 'vBC': '100.00', 'pPIS': '1.65', 'vPIS': '1.65'}},
        'COFINS': {'COFINSAliq': {'CST': '01', 'vBC': '100.00', 'pCOFINS': '7.60', 'vCOFINS': '7.60'}},
    }


class DfeClassificacaoHelpersTest(TestCase):
    def test_helpers_homologacao_e_base_importada(self) -> None:
        nf_hom = NFeSaidaHistoricaImportada(
            tp_amb='2', cstat='100', status_documento='autorizada', cancelada=False,
        )
        nf_prod = NFeSaidaHistoricaImportada(
            tp_amb='1', cstat='100', status_documento='autorizada', cancelada=False,
        )
        self.assertFalse(pode_entrar_apuracao(nf_hom))
        self.assertFalse(pode_alimentar_precificacao(nf_hom))
        self.assertFalse(pode_gerar_efeito_operacional(nf_hom))
        self.assertFalse(pode_gerar_efeito_operacional(nf_prod))

        self.assertTrue(pode_entrar_apuracao(nf_prod))
        self.assertTrue(pode_alimentar_precificacao(nf_prod))

        nf_op_hom = NFeSaida(
            ambiente_emissao=NFeSaida.AmbienteEmissao.HOMOLOGACAO,
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            status='AUTORIZADA_HOMOLOGACAO',
        )
        self.assertFalse(pode_entrar_apuracao(nf_op_hom))
        self.assertFalse(pode_gerar_efeito_operacional(nf_op_hom))


class ApuracaoExclusaoHomologacao40101Test(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(razao_social='Cliente 40101', cnpj='22.222.222/0001-22')
        self.dh = _dh(2026, 3, 15)
        self.params = {
            'data_inicio': '2026-03-01',
            'data_fim': '2026-03-31',
            'tipo': 'SAIDA',
            'fonte': 'TODOS',
        }

    def _criar_saida_hist(self, chave: str, *, tp_amb: str, valor: str = '500.00') -> NFeSaidaHistoricaImportada:
        nf = NFeSaidaHistoricaImportada.objects.create(
            chave_acesso=chave,
            numero=chave[-6:],
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb=tp_amb,
            cstat='100',
            valor_total_nf=Decimal(valor),
            valor_produtos=Decimal(valor),
        )
        ItemNFeSaidaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '5102', 'NCM': '84818099', 'vProd': valor},
            imposto_json=_item_icms(),
        )
        return nf

    def _criar_entrada_hist(self, chave: str, *, tp_amb: str) -> NFeEntradaHistoricaImportada:
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=chave,
            numero=chave[-6:],
            serie='1',
            modelo='55',
            dh_emissao=self.dh,
            tp_amb=tp_amb,
            cstat='100',
            valor_total_nf=Decimal('300.00'),
        )
        ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '1102', 'NCM': '84818099', 'vProd': '300.00'},
            imposto_json=_item_icms(),
        )
        return nf

    def test_nfe_saida_homologacao_autorizada_nao_entra_apuracao(self) -> None:
        self._criar_saida_hist('3' * 44, tp_amb='2', valor='999.00')
        pl = build_apuracao_fiscal({**self.params, 'fonte': 'HISTORICOS'})
        self.assertEqual(pl['cards']['notas_saida'], 0)
        self.assertAlmostEqual(pl['cards']['valor_saidas'], 0.0, places=2)

    def test_nfe_saida_importada_producao_entra_apuracao(self) -> None:
        self._criar_saida_hist('4' * 44, tp_amb='1', valor='500.00')
        pl = build_apuracao_fiscal({**self.params, 'fonte': 'HISTORICOS'})
        self.assertEqual(pl['cards']['notas_saida'], 1)
        self.assertAlmostEqual(pl['cards']['valor_saidas'], 500.0, places=2)

    def test_nfe_entrada_importada_homologacao_nao_entra(self) -> None:
        self._criar_entrada_hist('5' * 44, tp_amb='2')
        pl = build_apuracao_fiscal(
            {**self.params, 'tipo': 'ENTRADA', 'fonte': 'HISTORICOS'},
        )
        self.assertEqual(pl['cards']['notas_entrada'], 0)

    def test_nfe_entrada_importada_producao_entra(self) -> None:
        self._criar_entrada_hist('6' * 44, tp_amb='1')
        pl = build_apuracao_fiscal(
            {**self.params, 'tipo': 'ENTRADA', 'fonte': 'HISTORICOS'},
        )
        self.assertEqual(pl['cards']['notas_entrada'], 1)
        self.assertAlmostEqual(pl['cards']['valor_entradas'], 300.0, places=2)

    def test_nfe_saida_operacional_homologacao_nao_entra(self) -> None:
        NFeSaida.objects.create(
            numero='HOM-40101',
            cliente=self.cliente,
            data=date(2026, 3, 15),
            valor_total=Decimal('1200.00'),
            status='AUTORIZADA_HOMOLOGACAO',
            ambiente_emissao=NFeSaida.AmbienteEmissao.HOMOLOGACAO,
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            cstat_autorizacao='100',
        )
        pl = build_apuracao_fiscal({**self.params, 'fonte': 'OPERACIONAIS'})
        self.assertEqual(pl['cards']['notas_saida'], 0)

    def test_nfe_saida_operacional_emitida_entra(self) -> None:
        NFeSaida.objects.create(
            numero='PROD-40101',
            cliente=self.cliente,
            data=date(2026, 3, 15),
            valor_total=Decimal('800.00'),
            status='EMITIDA',
            ambiente_emissao=NFeSaida.AmbienteEmissao.PRODUCAO,
        )
        pl = build_apuracao_fiscal({**self.params, 'fonte': 'OPERACIONAIS'})
        self.assertEqual(pl['cards']['notas_saida'], 1)
        self.assertAlmostEqual(pl['cards']['valor_saidas'], 800.0, places=2)

    def test_filtro_todos_exclui_homologacao(self) -> None:
        self._criar_saida_hist('7' * 44, tp_amb='2', valor='999.00')
        self._criar_saida_hist('8' * 44, tp_amb='1', valor='400.00')
        pl = build_apuracao_fiscal(self.params)
        self.assertEqual(pl['cards']['notas_saida'], 1)
        self.assertAlmostEqual(pl['cards']['valor_saidas'], 400.0, places=2)

    def test_cte_homologacao_nao_escaneado_reforma(self) -> None:
        CTeHistoricoImportado.objects.create(
            chave_acesso='9' * 44,
            numero='1',
            dh_emissao=self.dh,
            tp_amb='2',
            cstat='100',
            valor_total_servico=Decimal('150.00'),
            imposto_json={'IBSCBS': {'gIBSCBS': {'vBC': '10', 'gCBS': {'vCBS': '99'}}}},
        )
        pl = build_apuracao_fiscal({**self.params, 'tipo': 'AMBOS'})
        self.assertEqual(pl['fontes'].get('ctes_historicos_escaneados_reforma', 0), 0)

    def test_rascunho_operacional_nao_entra(self) -> None:
        NFeSaida.objects.create(
            numero='RASC-40101',
            cliente=self.cliente,
            data=date(2026, 3, 15),
            valor_total=Decimal('50.00'),
            status='RASCUNHO',
        )
        pl = build_apuracao_fiscal({**self.params, 'fonte': 'OPERACIONAIS'})
        self.assertEqual(pl['cards']['notas_saida'], 0)
