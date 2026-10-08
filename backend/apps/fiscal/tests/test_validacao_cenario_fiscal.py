"""NF-e Saída — validação de itens contra o Cenário Fiscal vigente (item 3.1).

Cobertura:
- Item coberto pelo cenário: snapshot alinhado → info com regra vigente.
- Snapshot desalinhado (CFOP/CST divergentes da regra vigente): alerta.
- NCM/rota sem cobertura no cenário: pendência bloqueante.
- Resultado injetado em `validar_nfe_saida_para_emissao` (`cenario_fiscal`)
  e em `montar_conferencia_nfe_saida` (`cenario_vigente` por item).
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.tests.test_nfe_saida_faturamento import _pedido_item
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _regra_vigente_sp_rj(cenario=None, *, cfop='5102', cst_icms='00', ncm='84818200'):
    cenario = cenario or garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'Venda SP-RJ',
            'cfop_venda': cfop,
            'cst_icms': cst_icms,
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
        },
    )
    return regra


class ValidacaoCenarioFiscalItemTests(TestCase):
    def setUp(self):
        self.pedido, self.item_pedido = _pedido_item()
        # Gera NF-e rascunho com o item coberto pelo NCM 84818200 (SP->RJ).
        from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto

        fat = _faturamento_pronto(self.pedido, self.item_pedido)
        from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento

        res = gerar_nfe_saida_from_faturamento(self.pedido, fat.pk)
        self.nf = NFeSaida.objects.get(pk=res['nfe_saida_id'])
        self.item = self.nf.itens.first()

    def _validar(self):
        return validar_nfe_saida_para_emissao(self.nf, modo='leve')

    def test_item_coberto_snapshpt_alinhado(self):
        regra = _regra_vigente_sp_rj(cfop='5102', cst_icms='00')
        self.item.snapshot_fiscal = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'regra_fiscal_saida_id': regra.pk,
            'regra_fiscal_saida_nome': regra.nome,
            'cenario_fiscal_saida_id': regra.cenario_id,
            'cenario_fiscal_saida_nome': regra.cenario.nome,
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
            'aliquota_icms': '18',
            'cst_pis': '01',
            'aliquota_pis': '1.65',
            'cst_cofins': '01',
            'aliquota_cofins': '7.6',
        }
        self.item.save(update_fields=['snapshot_fiscal'])

        resultado = self._validar()
        cf = resultado.get('cenario_fiscal') or {}
        por_item = cf.get('por_item', [])
        self.assertEqual(len(por_item), 1)
        self.assertFalse(por_item[0]['divergente'], por_item[0]['mensagens'])
        self.assertEqual(por_item[0]['cfop_vigente'], '5102')
        self.assertEqual(por_item[0]['cst_vigente'], '00')
        self.assertTrue(por_item[0]['regra_nome'])
        pendencias_fiscais = [
            m for m in resultado['grupos'].get('fiscal', [])
            if m['tipo'] == 'PENDENCIA' and 'CENARIO' in m['codigo']
        ]
        self.assertEqual(pendencias_fiscais, [])

    def test_snapshot_desalinhado_da_regra_vigente(self):
        _regra_vigente_sp_rj(cfop='5102', cst_icms='00')
        self.item.snapshot_fiscal = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'ncm': '84818200',
            'cfop': '5101',
            'cst_icms': '60',
        }
        self.item.save(update_fields=['snapshot_fiscal'])

        resultado = self._validar()
        cf = resultado.get('cenario_fiscal') or {}
        por_item = cf.get('por_item', [])
        self.assertTrue(por_item[0]['divergente'])
        alertas_divergentes = [
            m for m in resultado['grupos'].get('fiscal', [])
            if m.get('item_id') == self.item.pk and m['codigo'] == 'ITENS_CENARIO_SNAPSHOT_DESATUALIZADO'
        ]
        self.assertTrue(alertas_divergentes)

    def test_divergencia_bloqueia_no_modo_estrito_de_emissao(self):
        regra = _regra_vigente_sp_rj(cfop='5102', cst_icms='00')
        self.item.snapshot_fiscal = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'regra_fiscal_saida_id': regra.pk,
            'cenario_fiscal_saida_id': regra.cenario_id,
            'ncm': '84818200',
            'cfop': '5101',
            'cst_icms': '00',
            'aliquota_icms': '18',
            'cst_pis': '01',
            'aliquota_pis': '1.65',
            'cst_cofins': '01',
            'aliquota_cofins': '7.6',
        }
        self.item.save(update_fields=['snapshot_fiscal'])

        resultado = validar_nfe_saida_para_emissao(
            self.nf,
            modo='leve',
            bloquear_divergencia_cenario=True,
        )
        pendencias = [
            m for m in resultado['grupos'].get('fiscal', [])
            if m.get('item_id') == self.item.pk
            and m['codigo'] == 'ITENS_CENARIO_SNAPSHOT_DESATUALIZADO_BLOQUEANTE'
            and m['tipo'] == 'PENDENCIA'
        ]
        self.assertTrue(pendencias)
        self.assertFalse(resultado['pode_emitir'])

    def test_ncm_sem_cobertura_no_cenario(self):
        _regra_vigente_sp_rj(cfop='5102', cst_icms='00', ncm='84818200')
        # NCM do item é resolvido do produto/snapshot fiscal: trocar para um NCM
        # sem regra no cenário.
        produto = self.item.produto
        produto.ncm = '73072100'
        produto.save(update_fields=['ncm'])
        self.item.snapshot_fiscal = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'ncm': '73072100',
            'cfop': '5102',
            'cst_icms': '00',
        }
        self.item.save(update_fields=['snapshot_fiscal'])

        resultado = self._validar()
        pendencias = [
            m for m in resultado['grupos'].get('fiscal', [])
            if m.get('item_id') == self.item.pk and m['codigo'] == 'ITENS_CENARIO_SEM_COBERTURA'
        ]
        self.assertTrue(pendencias)
        self.assertFalse(resultado['pode_emitir'])

    def test_conferencia_expoe_regra_vigente_por_item(self):
        regra = _regra_vigente_sp_rj(cfop='5102', cst_icms='00')
        self.item.snapshot_fiscal = {
            'origem_regra_fiscal_saida': 'CENARIO_SAIDA',
            'regra_fiscal_saida_id': regra.pk,
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
        }
        self.item.save(update_fields=['snapshot_fiscal'])

        conferencia = montar_conferencia_nfe_saida(self.nf)
        linha = next(i for i in conferencia['itens'] if i['item_id'] == self.item.pk)
        vigente = linha['cenario_vigente']
        self.assertTrue(vigente['encontrada'])
        self.assertEqual(vigente['cfop_vigente'], '5102')
        self.assertEqual(vigente['cst_vigente'], '00')
        self.assertTrue(vigente['cenario_nome'])
