"""Motor e API de RegraFiscalEntrada (Fase 3.1 + 3.2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.fiscal.models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.fiscal.services.imposto_item_xml import extrair_tributos_item
from apps.regras_fiscais.cst_icms_perspectiva import normalizar_cst_icms_xml_para_entrada
from apps.regras_fiscais.cst_ipi_perspectiva import normalizar_cst_ipi_xml_para_entrada
from apps.regras_fiscais.cst_pis_cofins_perspectiva import normalizar_cst_pis_cofins_xml_para_entrada
from apps.regras_fiscais.tributos_nf_exibicao import tributos_nf_para_exibicao_entrada
from apps.regras_fiscais.entrada_fiscal import (
    MSG_SEM_REGRA_FISCAL_ENTRADA,
    SCORE_CFOP_ORIGEM,
    SCORE_NCM_EXATO,
    SCORE_PRODUTO,
    ContextoFiscalEntrada,
    avaliar_item_entrada_fiscal,
    calcular_score_especificidade_regra_entrada,
    descricao_criterios_regra_entrada,
    encontrar_regra_fiscal_entrada,
    montar_contexto_fiscal_entrada,
    montar_resumo_fiscal_conferencia,
    validar_bloqueio_fiscal_preparar_conferencia,
)
from apps.regras_fiscais.models import RegraFiscalEntrada


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


class CstIcmsPerspectivaTests(SimpleTestCase):
    CASOS = (
        ('00', '00', 'tributado integralmente'),
        ('10', '60', 'tributado + ST → ST retida'),
        ('20', '20', 'redução de BC'),
        ('30', '60', 'isento + ST → ST retida'),
        ('40', '40', 'isento'),
        ('41', '41', 'não tributado'),
        ('50', '50', 'suspensão'),
        ('51', '51', 'diferimento'),
        ('60', '60', 'cobrado anteriormente por ST'),
        ('70', '60', 'redução BC + ST → ST retida'),
        ('90', '90', 'outros'),
        ('210', '60', 'origem 2 + situação 10 → ST retida'),
        ('110', '60', 'origem 1 + situação 10 → ST retida'),
        ('000', '00', 'origem 0 + situação 00'),
        ('060', '60', 'origem 0 + situação 60'),
        ('230', '60', 'origem 2 + situação 30 → ST retida'),
        ('', '', 'vazio'),
    )

    def test_normalizar_cst_icms_xml_para_entrada(self):
        for entrada, saida, descricao in self.CASOS:
            with self.subTest(entrada=entrada, saida=saida, descricao=descricao):
                self.assertEqual(normalizar_cst_icms_xml_para_entrada(entrada), saida)


class CstIpiPerspectivaTests(SimpleTestCase):
    CASOS = (
        ('00', '00', 'recuperação de crédito (já entrada)'),
        ('01', '01', 'tributada alíquota zero (já entrada)'),
        ('02', '02', 'isenta (já entrada)'),
        ('03', '03', 'não tributada (já entrada)'),
        ('04', '04', 'imune (já entrada)'),
        ('05', '05', 'suspensão (já entrada)'),
        ('49', '49', 'outras entradas'),
        ('50', '00', 'saída tributada → crédito'),
        ('51', '01', 'saída alíquota zero → entrada'),
        ('52', '02', 'saída isenta → entrada'),
        ('53', '03', 'saída não tributada → entrada'),
        ('54', '04', 'saída imune → entrada'),
        ('55', '05', 'saída suspensão → entrada'),
        ('99', '49', 'outros'),
        ('', '', 'vazio'),
    )

    def test_normalizar_cst_ipi_xml_para_entrada(self):
        for entrada, saida, descricao in self.CASOS:
            with self.subTest(entrada=entrada, saida=saida, descricao=descricao):
                self.assertEqual(normalizar_cst_ipi_xml_para_entrada(entrada), saida)


class CstPisCofinsPerspectivaTests(SimpleTestCase):
    CASOS = (
        ('01', '50', 'tributável básica → direito crédito básica'),
        ('02', '51', 'alíquota diferenciada'),
        ('03', '52', 'por unidade'),
        ('04', '53', 'monofásica'),
        ('05', '54', 'monofásica com retenção'),
        ('06', '55', 'ST'),
        ('07', '56', 'alíquota zero'),
        ('08', '57', 'sem incidência'),
        ('09', '58', 'com suspensão'),
        ('49', '70', 'outras saídas → outras entradas'),
        ('50', '01', 'direito crédito básica (já entrada)'),
        ('51', '02', 'alíquota diferenciada (já entrada)'),
        ('52', '03', 'por unidade (já entrada)'),
        ('53', '04', 'monofásica (já entrada)'),
        ('54', '05', 'com retenção (já entrada)'),
        ('55', '06', 'ST (já entrada)'),
        ('56', '07', 'alíquota zero (já entrada)'),
        ('57', '08', 'sem incidência (já entrada)'),
        ('58', '09', 'com suspensão (já entrada)'),
        ('70', '49', 'outras entradas (já entrada)'),
        ('71', '50', 'crédito presumido (já entrada)'),
        ('72', '50', 'crédito presumido (já entrada)'),
        ('73', '50', 'crédito presumido (já entrada)'),
        ('74', '50', 'crédito presumido (já entrada)'),
        ('75', '50', 'crédito presumido (já entrada)'),
        ('98', '98', 'outras operações (já entrada)'),
        ('99', '99', 'outras operações (já entrada)'),
        ('', '', 'vazio'),
    )

    def test_normalizar_cst_pis_cofins_xml_para_entrada(self):
        for entrada, saida, descricao in self.CASOS:
            with self.subTest(entrada=entrada, saida=saida, descricao=descricao):
                self.assertEqual(normalizar_cst_pis_cofins_xml_para_entrada(entrada), saida)


class TributosNfExibicaoEntradaTests(SimpleTestCase):
    def test_converte_cst_saida_para_perspectiva_entrada(self):
        trib = extrair_tributos_item(
            {'CFOP': '1403', 'NCM': '73072200'},
            {
                'ICMS': {'ICMS10': {'orig': '2', 'CST': '10', 'pICMS': '18.00', 'vBC': '100'}},
                'IPI': {'IPINT': {'CST': '53'}},
                'PIS': {'PISAliq': {'CST': '01', 'pPIS': '0.65'}},
                'COFINS': {'COFINSAliq': {'CST': '01', 'pCOFINS': '3.00'}},
            },
        )
        exib = tributos_nf_para_exibicao_entrada(trib)
        self.assertEqual(exib['cst_icms'], '60')
        self.assertEqual(exib['cst_ipi'], '03')
        self.assertEqual(exib['cst_pis'], '50')
        self.assertEqual(exib['cst_cofins'], '50')


class EntradaFiscalMotorTests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='Forn RF', cnpj=_cnpj(), uf='SP')
        fam = FamiliaProduto.objects.create(
            codigo_figura='FRF',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao='Prod RF',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='RF-001',
            unidade='PC',
            ncm='84818099',
        )
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '1' * 42)[:44],
            numero='9001',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 3, 1, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
            emit_json={'enderEmit': {'UF': 'SP'}},
            dest_json={'enderDest': {'UF': 'RJ'}},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '6102', 'NCM': '84818099', 'qCom': '1', 'uCom': 'PC'},
            imposto_json={'ICMS': {'ICMS00': {'CST': '00', 'vBC': '100', 'vICMS': '18'}}},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        self.linha.produto = self.prod
        self.linha.save(update_fields=['produto'])
        self.ctx = ContextoFiscalEntrada(uf_origem='SP', uf_destino='RJ', fornecedor_id=self.forn.id)

    def test_sem_regra_retorna_sem_regra(self):
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [])
        self.assertEqual(r['status'], 'SEM_REGRA')
        self.assertIsNone(r['regra_id'])
        self.assertIn(MSG_SEM_REGRA_FISCAL_ENTRADA, r['mensagens'][0])

    def test_match_por_cfop(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Compra 6102',
            codigo='C6102',
            ativo=True,
            prioridade=10,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['regra_id'], regra.id)

    def test_ncm_exato_vence_cfop_generico_por_score(self):
        generica = RegraFiscalEntrada.objects.create(
            nome='CFOP genérico',
            ativo=True,
            prioridade=100,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
            mensagem_padrao='genérica',
        )
        especifica = RegraFiscalEntrada.objects.create(
            nome='CFOP+NCM',
            ativo=True,
            prioridade=1,
            cfop='6102',
            ncm='84818099',
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
            mensagem_padrao='específica',
        )
        regras = list(RegraFiscalEntrada.objects.filter(ativo=True).order_by('prioridade', 'id'))
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, regras)
        self.assertEqual(r['regra_id'], especifica.id)
        self.assertEqual(r['status'], 'ALERTA')
        self.assertGreater(r['regra_score_especificidade'], SCORE_NCM_EXATO)

    def test_prioridade_maior_vence(self):
        baixa = RegraFiscalEntrada.objects.create(
            nome='Baixa',
            ativo=True,
            prioridade=1,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        alta = RegraFiscalEntrada.objects.create(
            nome='Alta',
            ativo=True,
            prioridade=100,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        regras = list(RegraFiscalEntrada.objects.filter(ativo=True).order_by('prioridade', 'id'))
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, regras)
        self.assertEqual(r['regra_id'], alta.id)
        self.assertEqual(r['status'], 'BLOQUEADO')
        self.assertEqual(r['regra_prioridade'], 100)

    def test_regra_alerta_retorna_alerta(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Alerta',
            ativo=True,
            prioridade=10,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'ALERTA')

    def test_descricao_criterios_regra_entrada(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Crit',
            ativo=True,
            prioridade=1,
            cfop='6102',
            ncm='8481',
            ncm_prefixo=True,
            uf_origem='SP',
            uf_destino='RJ',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        texto = descricao_criterios_regra_entrada(regra)
        self.assertIn('CFOP orig. 6102', texto)
        self.assertIn('prefixo', texto)
        self.assertIn('SP→RJ', texto)

    def test_montar_resumo_fiscal_conferencia(self):
        resumo = montar_resumo_fiscal_conferencia(
            [
                {'status': 'OK', 'movimenta_estoque': True, 'exige_certificado_fornecedor': False},
                {'status': 'ALERTA', 'movimenta_estoque': False, 'exige_certificado_fornecedor': True},
                {'status': 'SEM_REGRA', 'movimenta_estoque': None, 'exige_certificado_fornecedor': None},
                {'status': 'BLOQUEADO', 'movimenta_estoque': True, 'exige_certificado_fornecedor': True},
            ],
            self.ctx,
            linhas_ignoradas=2,
        )
        self.assertEqual(resumo['total_itens'], 4)
        self.assertEqual(resumo['ok'], 1)
        self.assertEqual(resumo['alerta'], 1)
        self.assertEqual(resumo['sem_regra'], 1)
        self.assertEqual(resumo['bloqueado'], 1)
        self.assertEqual(resumo['movimenta_estoque'], 2)
        self.assertEqual(resumo['exige_certificado_fornecedor'], 2)
        self.assertEqual(resumo['ignorados'], 2)
        self.assertEqual(resumo['uf_origem'], 'SP')
        self.assertEqual(resumo['uf_destino'], 'RJ')

    def test_regra_apenas_cfop_legado_casa_apos_limpar_origem(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Legado CFOP',
            ativo=True,
            prioridade=10,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        RegraFiscalEntrada.objects.filter(pk=regra.pk).update(cfop_origem='')
        regra.refresh_from_db()
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['regra_id'], regra.id)

    def test_match_por_cfop_origem(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Interno',
            descricao_cenario='Compra interestadual 6102',
            ativo=True,
            prioridade=10,
            cfop_origem='6102',
            cfop_entrada='1102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['cfop_entrada_esperado'], '1102')
        self.assertEqual(r['descricao_cenario'], 'Compra interestadual 6102')

    def test_migration_popula_cfop_origem_a_partir_de_cfop(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Mig',
            ativo=True,
            prioridade=1,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        regra.refresh_from_db()
        self.assertEqual(regra.cfop_origem, '6102')

    def test_cfop_entrada_nao_bloqueia_preparar(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Entrada esp',
            ativo=True,
            prioridade=10,
            cfop_origem='6102',
            cfop_entrada='1102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['cfop_entrada_esperado'], '1102')
        self.assertNotEqual(r['status'], 'BLOQUEADO')
        bloqueios = validar_bloqueio_fiscal_preparar_conferencia(
            self.conf,
            list(self.conf.itens.select_related('item_nfe_historico').all()),
        )
        self.assertEqual(bloqueios, [])

    def test_cst_ipi_extraido_do_xml(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00'}},
            'IPI': {'IPITrib': {'CST': '49', 'vIPI': '5.00'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='IPI',
            ativo=True,
            prioridade=10,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['cst_ipi_nf'], '49')

    def test_cst_divergente_gera_mensagem(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='CST',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_icms_esperado='10',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any('CST' in m for m in r['mensagens']))
        self.assertTrue(any(d['campo'] == 'cst_icms' for d in r['divergencias']))

    def _regra_cst_entrada(self, cst_esperado: str) -> RegraFiscalEntrada:
        return RegraFiscalEntrada.objects.create(
            nome=f'CST entrada {cst_esperado}',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_icms_esperado=cst_esperado,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )

    def _set_cst_icms_xml(self, cst: str) -> None:
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {f'ICMS{cst}': {'CST': cst, 'vBC': '100', 'vICMS': '0'}},
        }
        item_nf.save(update_fields=['imposto_json'])

    def _set_icms_xml_regime(
        self,
        *,
        cst: str = '',
        csosn: str = '',
        orig: str = '',
    ) -> None:
        item_nf = self.linha.item_nfe_historico
        if csosn:
            bloco = {f'ICMSSN{csosn}': {'CSOSN': csosn, 'vBC': '100'}}
        else:
            tag = f'ICMS{cst}' if len(cst) > 2 else f'ICMS{cst.zfill(2)}'
            body: dict[str, str] = {'CST': cst, 'vBC': '100', 'vICMS': '0'}
            if orig:
                body['orig'] = orig
            bloco = {tag: body}
        item_nf.imposto_json = {'ICMS': bloco}
        item_nf.save(update_fields=['imposto_json'])

    def test_extrair_tributos_separa_cst_e_csosn(self):
        trib_cst = extrair_tributos_item(
            {'CFOP': '1403'},
            {'ICMS': {'ICMS10': {'orig': '2', 'CST': '10', 'vBC': '100'}}},
        )
        self.assertEqual(trib_cst['cst_icms'], '10')
        self.assertEqual(trib_cst['csosn'], '')

        trib_sn = extrair_tributos_item(
            {'CFOP': '1403'},
            {'ICMS': {'ICMSSN500': {'CSOSN': '500', 'vBC': '100'}}},
        )
        self.assertEqual(trib_sn['cst_icms'], '')
        self.assertEqual(trib_sn['csosn'], '500')

    def test_nota_regime_normal_nao_diverge_csosn_da_regra(self):
        self._set_icms_xml_regime(orig='2', cst='10')
        regra = RegraFiscalEntrada.objects.create(
            nome='CST+CSOSN na regra',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_icms_esperado='060',
            csosn_esperado='201',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertFalse(any(d['campo'] == 'csosn' for d in r['divergencias']))

    def test_nota_simples_csosn_500_nao_diverge_cst_da_regra(self):
        self._set_icms_xml_regime(csosn='500')
        regra = RegraFiscalEntrada.objects.create(
            nome='Simples 500',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_icms_esperado='060',
            csosn_esperado='500',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertFalse(any(d['campo'] == 'cst_icms' for d in r['divergencias']))

    def test_cst_ausente_na_nota_com_regra_preenchida_alerta(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {'PIS': {'PISNT': {'CST': '07'}}}
        item_nf.save(update_fields=['imposto_json'])
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('060')])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'cst_icms' for d in r['divergencias']))

    def test_cst_ausente_na_nota_e_regra_sem_cst_ok(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {'PIS': {'PISNT': {'CST': '07'}}}
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='Sem CST',
            ativo=True,
            prioridade=10,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_origem_2_cst_10_casa_com_regra_060(self):
        self._set_icms_xml_regime(orig='2', cst='10')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('060')])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_cst_xml_70_normalizado_casa_com_regra_entrada_60(self):
        self._set_cst_icms_xml('70')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('60')])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_cst_icms_30_normalizado_casa_com_regra_entrada_60(self):
        self._set_cst_icms_xml('30')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('60')])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_cst_xml_00_vs_regra_entrada_20_continua_alerta(self):
        self._set_cst_icms_xml('00')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('20')])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'cst_icms' for d in r['divergencias']))

    def test_regra_cst_060_vs_xml_210_normalizado_ok(self):
        self._set_cst_icms_xml('210')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('060')])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_regra_cst_060_vs_xml_060_ok(self):
        self._set_cst_icms_xml('060')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('060')])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_regra_cst_60_vs_xml_060_ok(self):
        self._set_cst_icms_xml('060')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('60')])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_regra_cst_00_vs_xml_210_continua_alerta(self):
        self._set_cst_icms_xml('210')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_cst_entrada('00')])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'cst_icms' for d in r['divergencias']))

    def _regra_impostos_federais(
        self,
        *,
        cst_ipi: str = '',
        cst_pis: str = '',
        cst_cofins: str = '',
    ) -> RegraFiscalEntrada:
        return RegraFiscalEntrada.objects.create(
            nome='Federais',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_ipi_esperado=cst_ipi,
            cst_pis_esperado=cst_pis,
            cst_cofins_esperado=cst_cofins,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )

    def _set_impostos_federais_xml(self, *, cst_ipi: str = '', cst_pis: str = '') -> None:
        item_nf = self.linha.item_nfe_historico
        imposto: dict = {
            'ICMS': {'ICMS00': {'CST': '00', 'vBC': '100', 'vICMS': '0'}},
        }
        if cst_ipi:
            imposto['IPI'] = {'IPINT': {'CST': cst_ipi}}
        if cst_pis:
            imposto['PIS'] = {'PISNT': {'CST': cst_pis}}
        item_nf.imposto_json = imposto
        item_nf.save(update_fields=['imposto_json'])

    def test_nota_cst_ipi_53_casa_com_regra_ipi_03(self):
        self._set_impostos_federais_xml(cst_ipi='53')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_impostos_federais(cst_ipi='03')])
        self.assertEqual(r['status'], 'OK')
        self.assertFalse(any(d['campo'] == 'cst_ipi' for d in r['divergencias']))

    def test_nota_cst_pis_50_casa_com_regra_pis_01(self):
        self._set_impostos_federais_xml(cst_pis='50')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_impostos_federais(cst_pis='01')])
        self.assertEqual(r['status'], 'OK')
        self.assertFalse(any(d['campo'] == 'cst_pis' for d in r['divergencias']))

    def test_nota_cst_ipi_53_vs_regra_ipi_00_continua_alerta(self):
        self._set_impostos_federais_xml(cst_ipi='53')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [self._regra_impostos_federais(cst_ipi='00')])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'cst_ipi' for d in r['divergencias']))

    def _regra_cfop_ncm_base(self, nome: str, **kwargs) -> RegraFiscalEntrada:
        dados = dict(
            nome=nome,
            ativo=True,
            prioridade=10,
            cfop='6102',
            ncm='84818099',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        dados.update(kwargs)
        return RegraFiscalEntrada.objects.create(**dados)

    def test_selecao_por_menor_divergencia_ipi_escolhe_regra_03(self):
        regra_ipi_00 = self._regra_cfop_ncm_base(
            'IPI 00',
            prioridade=100,
            cst_icms_esperado='00',
            cst_ipi_esperado='00',
        )
        regra_ipi_03 = self._regra_cfop_ncm_base(
            'IPI 03',
            prioridade=1,
            cst_icms_esperado='00',
            cst_ipi_esperado='03',
        )
        self._set_impostos_federais_xml(cst_ipi='53')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra_ipi_00, regra_ipi_03])
        self.assertEqual(r['regra_id'], regra_ipi_03.id)
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_selecao_prefere_regra_com_ipi_vazio_quando_outra_diverge(self):
        regra_sem_ipi = self._regra_cfop_ncm_base(
            'Sem IPI',
            prioridade=1,
            cst_icms_esperado='00',
            cst_ipi_esperado='',
        )
        regra_ipi_errado = self._regra_cfop_ncm_base(
            'IPI errado',
            prioridade=100,
            cst_icms_esperado='00',
            cst_ipi_esperado='00',
        )
        self._set_impostos_federais_xml(cst_ipi='53')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra_sem_ipi, regra_ipi_errado])
        self.assertEqual(r['regra_id'], regra_sem_ipi.id)
        self.assertEqual(r['status'], 'OK')

    def test_selecao_escolhe_regra_com_mais_cst_corretos(self):
        regra_parcial = self._regra_cfop_ncm_base(
            'Parcial',
            prioridade=100,
            cst_icms_esperado='060',
            cst_ipi_esperado='00',
            cst_pis_esperado='99',
        )
        regra_completa = self._regra_cfop_ncm_base(
            'Completa',
            prioridade=1,
            cst_icms_esperado='060',
            cst_ipi_esperado='03',
            cst_pis_esperado='01',
        )
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS70': {'CST': '70', 'vBC': '100', 'vICMS': '0'}},
            'IPI': {'IPINT': {'CST': '53'}},
            'PIS': {'PISNT': {'CST': '50'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra_parcial, regra_completa])
        self.assertEqual(r['regra_id'], regra_completa.id)
        self.assertEqual(r['status'], 'OK')

    def test_selecao_regra_unica_comportamento_inalterado(self):
        regra = self._regra_cfop_ncm_base('Única', cst_icms_esperado='00')
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['regra_id'], regra.id)
        self.assertEqual(r['status'], 'OK')

    def test_score_estrutural_maior_vence_independente_de_cst(self):
        generica = RegraFiscalEntrada.objects.create(
            nome='CFOP genérico CST ok',
            ativo=True,
            prioridade=1,
            cfop='6102',
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        especifica = RegraFiscalEntrada.objects.create(
            nome='NCM específico CST divergente',
            ativo=True,
            prioridade=100,
            cfop='6102',
            ncm='84818099',
            cst_icms_esperado='20',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [generica, especifica])
        self.assertEqual(r['regra_id'], especifica.id)
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'cst_icms' for d in r['divergencias']))

    def test_regra_antiga_sem_campos_novos_ok(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Antiga',
            ativo=True,
            prioridade=10,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['divergencias'], [])

    def test_aliquota_icms_vazia_nao_diverge(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Sem aliq',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_icms_esperado='00',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '12.00', 'vBC': '100', 'vICMS': '12'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')

    def test_aliquota_icms_igual_ok(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '18.00', 'vBC': '100', 'vICMS': '18'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='ICMS 18',
            ativo=True,
            prioridade=10,
            cfop='6102',
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'OK')
        self.assertEqual(r['impostos_esperados'].get('aliquota_icms'), '18.00')
        self.assertEqual(r['impostos_nf'].get('aliquota_icms'), '18.00')

    def test_aliquota_icms_divergente_alerta(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '12.00', 'vBC': '100', 'vICMS': '12'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='ICMS esp',
            ativo=True,
            prioridade=10,
            cfop='6102',
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'ALERTA')
        div = next(d for d in r['divergencias'] if d['campo'] == 'aliquota_icms')
        self.assertEqual(div['esperado'], '18.00')
        self.assertEqual(div['informado'], '12.00')

    def test_cst_ipi_comparado(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '18'}},
            'IPI': {'IPITrib': {'CST': '49'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='IPI CST',
            ativo=True,
            prioridade=10,
            cfop='6102',
            cst_ipi_esperado='50',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'cst_ipi' for d in r['divergencias']))

    def test_bloqueio_apenas_com_severidade_bloqueio(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '12.00', 'vBC': '100'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='Bloq',
            ativo=True,
            prioridade=10,
            cfop='6102',
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'BLOQUEADO')
        bloqueios = validar_bloqueio_fiscal_preparar_conferencia(
            self.conf,
            list(self.conf.itens.select_related('item_nfe_historico').all()),
        )
        self.assertEqual(len(bloqueios), 1)

    def test_resultado_expoe_impostos_e_divergencias(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '18.00'}},
            'PIS': {'PISAliq': {'CST': '50', 'pPIS': '1.65'}},
            'COFINS': {'COFINSAliq': {'CST': '50', 'pCOFINS': '7.60'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='Completa',
            ativo=True,
            prioridade=10,
            cfop='6102',
            aliquota_icms=Decimal('18'),
            aliquota_pis=Decimal('1.65'),
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertIn('aliquota_icms', r['impostos_nf'])
        self.assertIn('aliquota_pis', r['impostos_nf'])
        self.assertIn('aliquota_icms', r['impostos_esperados'])
        self.assertIsInstance(r['divergencias'], list)


class EspecificidadeMatchTests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='Forn ESP', cnpj=_cnpj(), uf='SP')
        fam = FamiliaProduto.objects.create(
            codigo_figura='FESP',
            descricao_base='Fam',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        self.prod = Produto.objects.create(
            familia=fam,
            descricao='Prod ESP',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='ESP-001',
            unidade='PC',
            ncm='84818099',
        )
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '3' * 42)[:44],
            numero='9003',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 3, 3, 10, 0)),
            valor_total_nf=Decimal('100'),
            fornecedor_emitente=self.forn,
            emit_json={'enderEmit': {'UF': 'SP'}},
            dest_json={'enderDest': {'UF': 'RJ'}},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '6102', 'NCM': '84818099', 'qCom': '1', 'uCom': 'PC'},
            imposto_json={'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '18'}}},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.linha, _ = self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        self.linha.produto = self.prod
        self.linha.save(update_fields=['produto'])
        self.ctx = ContextoFiscalEntrada(uf_origem='SP', uf_destino='RJ', fornecedor_id=self.forn.id)

    def test_produto_vence_ncm_com_prioridade_menor(self):
        por_ncm = RegraFiscalEntrada.objects.create(
            nome='NCM',
            ativo=True,
            prioridade=100,
            cfop='6102',
            ncm='84818099',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        por_produto = RegraFiscalEntrada.objects.create(
            nome='Produto',
            ativo=True,
            prioridade=1,
            cfop='6102',
            produto=self.prod,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [por_ncm, por_produto])
        self.assertEqual(r['regra_id'], por_produto.id)
        self.assertIn('Produto específico', r['regra_match_motivos'])

    def test_ncm_exato_vence_ncm_prefixo(self):
        prefixo = RegraFiscalEntrada.objects.create(
            nome='Prefixo',
            ativo=True,
            prioridade=100,
            cfop='6102',
            ncm='8481',
            ncm_prefixo=True,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        exato = RegraFiscalEntrada.objects.create(
            nome='Exato',
            ativo=True,
            prioridade=1,
            cfop='6102',
            ncm='84818099',
            ncm_prefixo=False,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [prefixo, exato])
        self.assertEqual(r['regra_id'], exato.id)
        esp = calcular_score_especificidade_regra_entrada(
            exato,
            cfop_nf='6102',
            ncm_nf='84818099',
            contexto=self.ctx,
            produto_id=self.prod.id,
        )
        self.assertIsNotNone(esp)
        assert esp is not None
        self.assertGreaterEqual(esp.score, SCORE_NCM_EXATO + SCORE_CFOP_ORIGEM)

    def test_ncm_prefixo_vence_regra_geral(self):
        geral = RegraFiscalEntrada.objects.create(
            nome='Geral',
            ativo=True,
            prioridade=100,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        prefixo = RegraFiscalEntrada.objects.create(
            nome='Prefixo',
            ativo=True,
            prioridade=1,
            cfop='6102',
            ncm='8481',
            ncm_prefixo=True,
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [geral, prefixo])
        self.assertEqual(r['regra_id'], prefixo.id)
        self.assertIn('NCM prefixo', r['regra_match_motivos'])

    def test_uf_origem_destino_participam_do_score(self):
        geral = RegraFiscalEntrada.objects.create(
            nome='Geral',
            ativo=True,
            prioridade=100,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        com_uf = RegraFiscalEntrada.objects.create(
            nome='UF',
            ativo=True,
            prioridade=1,
            cfop='6102',
            uf_origem='SP',
            uf_destino='RJ',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [geral, com_uf])
        self.assertEqual(r['regra_id'], com_uf.id)
        self.assertIn('UF origem', r['regra_match_motivos'])
        self.assertIn('UF destino', r['regra_match_motivos'])

    def test_prioridade_desempata_mesmo_score(self):
        baixa = RegraFiscalEntrada.objects.create(
            nome='Baixa',
            ativo=True,
            prioridade=5,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        alta = RegraFiscalEntrada.objects.create(
            nome='Alta',
            ativo=True,
            prioridade=50,
            cfop='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        match = encontrar_regra_fiscal_entrada(
            [baixa, alta],
            cfop_nf='6102',
            ncm_nf='84818099',
            contexto=self.ctx,
            produto_id=self.prod.id,
        )
        self.assertIsNotNone(match)
        assert match is not None
        regra, _esp = match
        self.assertEqual(regra.id, alta.id)

    def test_cfop_origem_no_score(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='CFOP',
            ativo=True,
            prioridade=1,
            cfop_origem='6102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        esp = calcular_score_especificidade_regra_entrada(
            regra,
            cfop_nf='6102',
            ncm_nf='84818099',
            contexto=self.ctx,
            produto_id=self.prod.id,
        )
        self.assertIsNotNone(esp)
        assert esp is not None
        self.assertIn('CFOP origem', esp.motivos)
        self.assertGreaterEqual(esp.score, SCORE_CFOP_ORIGEM)

    def test_resultado_expoe_score_motivos_e_prioridade(self):
        regra = RegraFiscalEntrada.objects.create(
            nome='Esp',
            ativo=True,
            prioridade=42,
            cfop='6102',
            ncm='84818099',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['regra_prioridade'], 42)
        self.assertGreater(r['regra_score_especificidade'], 0)
        self.assertTrue(r['regra_match_motivos'])

    def test_divergencia_imposto_apos_match_por_score(self):
        item_nf = self.linha.item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '12.00', 'vBC': '100'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        regra = RegraFiscalEntrada.objects.create(
            nome='Aliq',
            ativo=True,
            prioridade=1,
            cfop='6102',
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
        )
        r = avaliar_item_entrada_fiscal(self.linha, self.ctx, [regra])
        self.assertEqual(r['status'], 'ALERTA')
        self.assertTrue(any(d['campo'] == 'aliquota_icms' for d in r['divergencias']))


class ConferenciaResultadoFiscalAPITests(TestCase):
    def setUp(self):
        self.forn = Fornecedor.objects.create(razao_social='Forn API', cnpj=_cnpj(), uf='MG')
        nf = NFeEntradaHistoricaImportada.objects.create(
            chave_acesso=('35' + '2' * 42)[:44],
            numero='9002',
            serie='1',
            modelo='55',
            dh_emissao=timezone.make_aware(datetime(2026, 3, 2, 10, 0)),
            valor_total_nf=Decimal('50'),
            fornecedor_emitente=self.forn,
            emit_json={'UF': 'MG'},
            dest_json={'UF': 'SP'},
        )
        item_nf = ItemNFeEntradaHistoricaImportada.objects.create(
            nf=nf,
            n_item=1,
            prod_json={'CFOP': '1102', 'NCM': '73071100'},
            imposto_json={},
        )
        self.conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
        self.conf.itens.get_or_create(item_nfe_historico=item_nf)
        RegraFiscalEntrada.objects.create(
            nome='Compra 1102',
            ativo=True,
            prioridade=10,
            cfop='1102',
            severidade=RegraFiscalEntrada.Severidade.INFORMATIVO,
        )
        user = get_user_model().objects.create_user('rf_api', 'rf@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.url = reverse('nf-entrada-hist-importada-conferencia', kwargs={'pk': nf.id})
        self.url_prep = reverse('nf-entrada-hist-importada-preparar-estoque', kwargs={'pk': nf.id})

    def test_get_conferencia_expoe_resultado_fiscal(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        item = r.json()['itens'][0]
        self.assertIn('resultado_fiscal', item)
        self.assertEqual(item['resultado_fiscal']['status'], 'OK')
        self.assertEqual(item['resultado_fiscal']['regra_nome'], 'Compra 1102')
        self.assertEqual(item['resultado_fiscal']['cfop_nf'], '1102')

    def test_get_conferencia_expoe_impostos_e_divergencias(self):
        item_nf = self.conf.itens.first().item_nfe_historico
        item_nf.imposto_json = {
            'ICMS': {'ICMS00': {'CST': '00', 'pICMS': '12.00', 'vBC': '100'}},
        }
        item_nf.save(update_fields=['imposto_json'])
        RegraFiscalEntrada.objects.filter(cfop='1102').update(
            aliquota_icms=Decimal('18'),
            severidade=RegraFiscalEntrada.Severidade.ALERTA,
        )
        r = self.client.get(self.url)
        rf = r.json()['itens'][0]['resultado_fiscal']
        self.assertIn('impostos_nf', rf)
        self.assertIn('impostos_esperados', rf)
        self.assertIn('divergencias', rf)
        self.assertTrue(any(d['campo'] == 'aliquota_icms' for d in rf['divergencias']))

    def test_get_conferencia_expoe_cfop_entrada_e_cenario(self):
        RegraFiscalEntrada.objects.filter(cfop='1102').update(
            cfop_origem='1102',
            cfop_entrada='1403',
            descricao_cenario='Compra interna RJ',
        )
        r = self.client.get(self.url)
        rf = r.json()['itens'][0]['resultado_fiscal']
        self.assertEqual(rf['cfop_entrada_esperado'], '1403')
        self.assertEqual(rf['descricao_cenario'], 'Compra interna RJ')

    def test_get_conferencia_expoe_resumo_fiscal(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        resumo = r.json()['resumo_fiscal']
        self.assertEqual(resumo['total_itens'], 1)
        self.assertEqual(resumo['ok'], 1)
        self.assertEqual(resumo['sem_regra'], 0)

    def test_resumo_fiscal_item_sem_regra(self):
        RegraFiscalEntrada.objects.filter(cfop='1102').delete()
        r = self.client.get(self.url)
        resumo = r.json()['resumo_fiscal']
        self.assertEqual(resumo['sem_regra'], 1)
        self.assertEqual(resumo['ok'], 0)
        msg = r.json()['itens'][0]['resultado_fiscal']['mensagens'][0]
        self.assertIn('CFOP/NCM/UF', msg)

    def test_resumo_contadores_movimenta_estoque_e_certificado(self):
        RegraFiscalEntrada.objects.filter(cfop='1102').update(
            movimenta_estoque=True,
            exige_certificado_fornecedor=True,
        )
        r = self.client.get(self.url)
        resumo = r.json()['resumo_fiscal']
        self.assertEqual(resumo['movimenta_estoque'], 1)
        self.assertEqual(resumo['exige_certificado_fornecedor'], 1)

    def test_bloqueio_impede_preparar_estoque(self):
        RegraFiscalEntrada.objects.filter(cfop='1102').update(
            severidade=RegraFiscalEntrada.Severidade.BLOQUEIO,
            mensagem_padrao='Operação não permitida',
        )
        fam = FamiliaProduto.objects.create(
            codigo_figura='FA',
            descricao_base='F',
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
            tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
            categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
        )
        prod = Produto.objects.create(
            familia=fam,
            descricao='P',
            modo_codigo=Produto.ModoCodigo.MANUAL,
            codigo_completo='P1',
            unidade='PC',
        )
        linha = self.conf.itens.first()
        self.client.post(
            self.url,
            {
                'itens': [
                    {
                        'id': linha.id,
                        'produto_id': prod.id,
                        'status': 'PRODUTO_VINCULADO',
                    },
                ],
            },
            format='json',
        )
        r = self.client.get(self.url)
        self.assertEqual(r.json()['itens'][0]['resultado_fiscal']['status'], 'BLOQUEADO')
        r_prep = self.client.post(self.url_prep, {}, format='json')
        self.assertEqual(r_prep.status_code, status.HTTP_400_BAD_REQUEST)
        body = r_prep.json()
        self.assertTrue(body.get('bloqueio_fiscal'))
        pendencias = ' '.join(body.get('pendencias') or [])
        self.assertIn('Item 1', pendencias)
        self.assertIn('1102', pendencias)
        self.assertIn('73071100', pendencias)
        self.assertIn('Compra 1102', pendencias)
        self.assertIn('Operação não permitida', pendencias)

    def test_alerta_nao_bloqueia_preparar_via_validador(self):
        regra = RegraFiscalEntrada.objects.get(cfop='1102')
        regra.severidade = RegraFiscalEntrada.Severidade.ALERTA
        regra.save(update_fields=['severidade'])
        bloqueios = validar_bloqueio_fiscal_preparar_conferencia(
            self.conf,
            list(self.conf.itens.select_related('item_nfe_historico').all()),
        )
        self.assertEqual(bloqueios, [])
