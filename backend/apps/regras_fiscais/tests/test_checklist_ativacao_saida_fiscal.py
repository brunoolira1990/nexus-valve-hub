"""Fase Saída 3.4 — checklist de prontidão para ativação global do cenário fiscal de saída."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import ItemProposta, Proposta
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida
from apps.regras_fiscais.saida_fiscal import (
    avaliar_prontidao_ativacao_cenario_saida,
    cobertura_propostas_fiscal_saida,
    comparar_regra_fiscal_saida_legado_cenario,
)


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(ncm: str) -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'CK{suf}',
        descricao_base='Fam checklist',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod checklist',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'CK-{suf}',
        unidade='PC',
        ncm=ncm,
    )


def _proposta_item(ncm: str, numero: str) -> None:
    emp = Empresa.objects.create(razao_social=f'Emit {numero}', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social=f'Cli {numero}', cnpj=_cnpj(), uf='RJ')
    hoje = date.today()
    prop = Proposta.objects.create(
        numero=numero,
        data=hoje,
        validade=hoje + timedelta(days=30),
        empresa_emitente=emp,
        cliente=cli,
        uf_origem='SP',
    )
    prod = _produto(ncm)
    ItemProposta.objects.create(
        proposta=prop,
        produto=prod,
        quantidade=Decimal('1'),
        valor_unitario=Decimal('100'),
    )


def _escopo_ncm(cenario, ncm: str) -> CenarioFiscalSaidaEscopo:
    return CenarioFiscalSaidaEscopo.objects.create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
    )


def _regra_saida(escopo, aliquota_icms: str = '18') -> RegraFiscalSaida:
    return RegraFiscalSaida.objects.create(
        escopo=escopo,
        cenario=escopo.cenario,
        ativo=True,
        uf_origem='SP',
        uf_destino='RJ',
        cfop_venda='5102',
        tipo_operacao='VENDA',
        cst_icms='00',
        aliquota_icms=Decimal(aliquota_icms),
        cst_ipi='50',
        aliquota_ipi=Decimal('5'),
        cst_pis='01',
        aliquota_pis=Decimal('1.65'),
        cst_cofins='01',
        aliquota_cofins=Decimal('7.6'),
    )


def _regra_legado(ncm: str, aliquota_icms: float = 18.0) -> RegraFiscal:
    return RegraFiscal.objects.create(
        ncm=ncm,
        uf_origem='SP',
        uf_destino='RJ',
        operacao='Saída',
        cfop='5102',
        cst_icms='00',
        aliquota_icms=aliquota_icms,
        cst_ipi='50',
        aliquota_ipi=5.0,
        cst_pis='01',
        aliquota_pis=1.65,
        cst_cofins='01',
        aliquota_cofins=7.6,
    )


class ChecklistAtivacaoSaidaTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()
        self.hoje = date.today()
        self.periodo = {
            'data_inicial': self.hoje - timedelta(days=1),
            'data_final': self.hoje,
            'limite': 500,
            'max_scan': 500,
        }

    def test_pode_ativar_cobertura_alta_divergencia_baixa(self):
        ncm = '84819001'
        escopo = _escopo_ncm(self.cenario, ncm)
        _regra_saida(escopo)
        _regra_legado(ncm)
        for i in range(12):
            _proposta_item(ncm, f'CK-OK-{i}')
        r = avaliar_prontidao_ativacao_cenario_saida(**self.periodo)
        self.assertEqual(r['status'], 'PODE_ATIVAR')
        self.assertGreaterEqual(Decimal(r['resumo']['percentual_cobertura_cenario']), Decimal('95'))
        codigos = {c['codigo']: c['status'] for c in r['criterios']}
        self.assertEqual(codigos['COBERTURA_MINIMA'], 'OK')
        self.assertEqual(codigos['DIVERGENCIAS'], 'OK')

    def test_atencao_amostra_pequena(self):
        ncm = '84819002'
        escopo = _escopo_ncm(self.cenario, ncm)
        _regra_saida(escopo)
        _regra_legado(ncm)
        _proposta_item(ncm, 'CK-AT-1')
        r = avaliar_prontidao_ativacao_cenario_saida(**self.periodo)
        self.assertEqual(r['status'], 'ATENCAO')
        amostra = next(c for c in r['criterios'] if c['codigo'] == 'AMOSTRA_MINIMA')
        self.assertEqual(amostra['status'], 'ATENCAO')
        self.assertTrue(any('amostra' in m.lower() for m in r['recomendacoes']))

    def test_nao_recomendado_cobertura_baixa(self):
        for i in range(12):
            ncm = f'848191{i:02d}'
            _proposta_item(ncm, f'CK-BAIXO-{i}')
        r = avaliar_prontidao_ativacao_cenario_saida(**self.periodo)
        self.assertEqual(r['status'], 'NAO_RECOMENDADO')
        cob = next(c for c in r['criterios'] if c['codigo'] == 'COBERTURA_MINIMA')
        self.assertEqual(cob['status'], 'NAO_RECOMENDADO')

    def test_nao_recomendado_divergencia_alta(self):
        for i in range(12):
            ncm = f'848192{i:02d}'
            escopo = _escopo_ncm(self.cenario, ncm)
            _regra_saida(escopo, aliquota_icms='18')
            _regra_legado(ncm, aliquota_icms=12.0)
            _proposta_item(ncm, f'CK-DIV-{i}')
        r = avaliar_prontidao_ativacao_cenario_saida(**self.periodo)
        self.assertEqual(r['status'], 'NAO_RECOMENDADO')
        div = next(c for c in r['criterios'] if c['codigo'] == 'DIVERGENCIAS')
        self.assertEqual(div['status'], 'NAO_RECOMENDADO')

    def test_sem_cenario_afeta_recomendacao(self):
        for i in range(12):
            ncm = f'848193{i:02d}'
            _regra_legado(ncm)
            _proposta_item(ncm, f'CK-SEM-{i}')
        r = avaliar_prontidao_ativacao_cenario_saida(**self.periodo)
        sem = next(c for c in r['criterios'] if c['codigo'] == 'SEM_CENARIO')
        self.assertIn(sem['status'], ('ATENCAO', 'NAO_RECOMENDADO'))
        self.assertTrue(r['lacunas_prioritarias'])

    def test_ambos_nao_encontrados_atencao(self):
        for i in range(12):
            ncm = f'848194{i:02d}'
            _proposta_item(ncm, f'CK-AMB-{i}')
        r = avaliar_prontidao_ativacao_cenario_saida(**self.periodo)
        ambos = next(c for c in r['criterios'] if c['codigo'] == 'AMBOS_NAO_ENCONTRADOS')
        self.assertIn(ambos['status'], ('ATENCAO', 'NAO_RECOMENDADO'))
        self.assertGreater(r['resumo']['ambos_nao_encontrados'], 0)

    def test_endpoint_read_only(self):
        user = get_user_model().objects.create_user('ck_api', 'ck@test.com', 'x')
        client = APIClient()
        client.force_authenticate(user)
        url = reverse('regrafiscal-saida-checklist-ativacao')
        r = client.get(url, {'data_inicial': str(self.periodo['data_inicial'])})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn(r.json()['status'], ('PODE_ATIVAR', 'ATENCAO', 'NAO_RECOMENDADO'))

    def test_filtros_respeitados(self):
        ncm_ok = '84819501'
        ncm_out = '84819599'
        escopo = _escopo_ncm(self.cenario, ncm_ok)
        _regra_saida(escopo)
        _regra_legado(ncm_ok)
        _proposta_item(ncm_ok, 'CK-FILT-1')
        _proposta_item(ncm_out, 'CK-FILT-2')
        r = avaliar_prontidao_ativacao_cenario_saida(
            data_inicial=self.periodo['data_inicial'],
            data_final=self.periodo['data_final'],
            ncm=ncm_ok,
            limite=500,
            max_scan=500,
        )
        self.assertEqual(r['resumo']['total_itens'], 1)

    def test_cobertura_fase_32_continua(self):
        ncm = '84819601'
        escopo = _escopo_ncm(self.cenario, ncm)
        _regra_saida(escopo)
        _regra_legado(ncm)
        _proposta_item(ncm, 'CK-COB')
        r = cobertura_propostas_fiscal_saida(**self.periodo)
        self.assertEqual(r['resumo']['total_itens'], 1)

    def test_comparativo_fase_31_continua(self):
        ncm = '84819701'
        escopo = _escopo_ncm(self.cenario, ncm)
        _regra_saida(escopo)
        _regra_legado(ncm)
        cmp = comparar_regra_fiscal_saida_legado_cenario(ncm=ncm, uf_origem='SP', uf_destino='RJ')
        self.assertEqual(cmp['status'], 'IGUAL')

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
    def test_flag_global_false_por_padrao(self):
        from django.conf import settings

        self.assertFalse(settings.USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS)
