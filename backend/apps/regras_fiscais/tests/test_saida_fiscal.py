"""Fase Saída 3 — motor fiscal de saída com fallback legado."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.comercial.pricing import find_regra_fiscal, find_regra_fiscal_saida_com_fallback
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import (
    CenarioFiscalSaidaEscopo,
    RegraFiscal,
    RegraFiscalSaida,
)
from apps.regras_fiscais.saida_fiscal import buscar_regra_fiscal_saida


def _criar_familia_produto(ncm: str = '84818099') -> Produto:
    fam = FamiliaProduto.objects.create(
        codigo_figura='FS3',
        descricao_base='Fam teste saída',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod teste saída',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo='SAIDA-T',
        unidade='PC',
        ncm=ncm,
    )


def _criar_regra_saida(
    escopo: CenarioFiscalSaidaEscopo,
    *,
    prioridade: int = 0,
    uf_origem: str = 'SP',
    uf_destino: str = 'RJ',
    destinatario_contribuinte: str = RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
    aliquota_icms: Decimal = Decimal('18'),
    cfop_venda: str = '5102',
) -> RegraFiscalSaida:
    return RegraFiscalSaida.objects.create(
        escopo=escopo,
        cenario=escopo.cenario,
        ativo=True,
        prioridade=prioridade,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        destinatario_contribuinte=destinatario_contribuinte,
        consumidor_final=consumidor_final,
        tipo_operacao=tipo_operacao,
        cfop_venda=cfop_venda,
        cst_icms='00',
        aliquota_icms=aliquota_icms,
        cst_pis='01',
        aliquota_pis=Decimal('1.65'),
        cst_cofins='01',
        aliquota_cofins=Decimal('7.6'),
    )


class SaidaFiscalMotorTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()

    def test_produto_vence_ncm(self):
        prod = _criar_familia_produto('84818099')
        escopo_ncm = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818099',
        )
        escopo_prod = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.PRODUTO,
            produto=prod,
        )
        _criar_regra_saida(escopo_ncm, aliquota_icms=Decimal('10'))
        regra_prod = _criar_regra_saida(escopo_prod, aliquota_icms=Decimal('20'))

        r = buscar_regra_fiscal_saida(
            produto_id=prod.pk,
            ncm='84818099',
            uf_origem='SP',
            uf_destino='RJ',
        )
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r['regra_id'], regra_prod.id)
        self.assertEqual(r['aliquota_icms'], '20.00')

    def test_ncm_exato_vence_prefixo(self):
        escopo_prefix = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM_PREFIXO,
            ncm='8481',
        )
        escopo_exato = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818099',
        )
        _criar_regra_saida(escopo_prefix, aliquota_icms=Decimal('12'))
        regra_exato = _criar_regra_saida(escopo_exato, aliquota_icms=Decimal('18'))

        r = buscar_regra_fiscal_saida(ncm='84818099', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r['regra_id'], regra_exato.id)
        self.assertEqual(r['aliquota_icms'], '18.00')

    def test_destinatario_contribuinte_casa(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='73071100',
        )
        _criar_regra_saida(
            escopo,
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE,
            aliquota_icms=Decimal('18'),
        )
        regra_nc = _criar_regra_saida(
            escopo,
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE,
            aliquota_icms=Decimal('7'),
            prioridade=1,
        )

        r_ok = buscar_regra_fiscal_saida(
            ncm='73071100',
            uf_origem='SP',
            uf_destino='RJ',
            destinatario_contribuinte='NAO_CONTRIBUINTE',
        )
        self.assertEqual(r_ok['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r_ok['regra_id'], regra_nc.id)

        r_fail = buscar_regra_fiscal_saida(
            ncm='73071100',
            uf_origem='SP',
            uf_destino='RJ',
            destinatario_contribuinte='CONTRIBUINTE',
        )
        self.assertEqual(r_fail['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r_fail['aliquota_icms'], '18.00')

    def test_destinatario_qualquer_casa_ambos(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='39174000',
        )
        regra = _criar_regra_saida(
            escopo,
            destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        )
        for dest in ('CONTRIBUINTE', 'NAO_CONTRIBUINTE', ''):
            r = buscar_regra_fiscal_saida(
                ncm='39174000',
                uf_origem='SP',
                uf_destino='RJ',
                destinatario_contribuinte=dest or None,
            )
            self.assertEqual(r['origem'], 'CENARIO_SAIDA', msg=dest)
            self.assertEqual(r['regra_id'], regra.id)

    def test_prioridade_desempata(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84811000',
        )
        _criar_regra_saida(escopo, prioridade=5, aliquota_icms=Decimal('12'))
        regra_alta = _criar_regra_saida(escopo, prioridade=50, aliquota_icms=Decimal('18'))

        r = buscar_regra_fiscal_saida(ncm='84811000', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['regra_id'], regra_alta.id)

    def test_cenario_encontrado_nao_usa_legado(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='40169300',
        )
        _criar_regra_saida(escopo, aliquota_icms=Decimal('18'))
        RegraFiscal.objects.create(
            ncm='40169300',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=99.0,
        )
        r = buscar_regra_fiscal_saida(ncm='40169300', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r['aliquota_icms'], '18.00')
        self.assertIsNone(r['regra_legada_id'])

    def test_fallback_legado_quando_cenario_vazio(self):
        legado = RegraFiscal.objects.create(
            ncm='73269090',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            cst_icms='00',
            aliquota_icms=12.0,
            aliquota_pis=1.65,
            aliquota_cofins=7.6,
            aliquota_ipi=0.0,
        )
        r = buscar_regra_fiscal_saida(ncm='73269090', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['origem'], 'LEGADO')
        self.assertEqual(r['regra_legada_id'], legado.id)
        self.assertIsNone(r['regra_id'])

    def test_nao_encontrada_sem_quebrar(self):
        r = buscar_regra_fiscal_saida(ncm='99999999', uf_origem='SP', uf_destino='RJ')
        self.assertEqual(r['origem'], 'NAO_ENCONTRADA')
        self.assertIsNone(r['regra_id'])
        self.assertIsNone(r['regra_legada_id'])
        self.assertTrue(r['mensagens'])


class SaidaFiscalPropostasFlagTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
    def test_propostas_flag_off_usa_apenas_legado(self):
        legado = RegraFiscal.objects.create(
            ncm='84139190',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84139190',
        )
        _criar_regra_saida(escopo, aliquota_icms=Decimal('99'))

        r = find_regra_fiscal_saida_com_fallback('84139190', 'SP', 'RJ', 'Saída')
        self.assertEqual(r['origem'], 'LEGADO')
        self.assertEqual(r['regra_legada_id'], legado.id)

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
    def test_propostas_flag_on_usa_cenario(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84149010',
        )
        regra = _criar_regra_saida(escopo, aliquota_icms=Decimal('18'))
        r = find_regra_fiscal_saida_com_fallback('84149010', 'SP', 'RJ', 'Saída')
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r['regra_id'], regra.id)


class SaidaFiscalAPITests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('saida_busca', 'busca@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = garantir_cenario_saida_padrao()
        self.url_buscar = reverse('regrafiscal-saida-buscar')
        self.url_legado = reverse('regrafiscal-buscar')

    def test_api_buscar_cenario_saida(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818095',
        )
        regra = _criar_regra_saida(escopo, cfop_venda='5102', aliquota_icms=Decimal('18'))
        r = self.client.get(
            self.url_buscar,
            {'ncm': '84818095', 'uf_origem': 'SP', 'uf_destino': 'RJ', 'tipo_operacao': 'VENDA'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['origem'], 'CENARIO_SAIDA')
        self.assertEqual(body['regra_id'], regra.id)
        self.assertEqual(body['cfop'], '5102')
        self.assertEqual(body['aliquota_icms'], '18.00')

    def test_api_buscar_fallback_legado(self):
        legado = RegraFiscal.objects.create(
            ncm='84818096',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='6102',
            aliquota_icms=12.0,
        )
        r = self.client.get(
            self.url_buscar,
            {'ncm': '84818096', 'uf_origem': 'SP', 'uf_destino': 'RJ'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['origem'], 'LEGADO')
        self.assertEqual(body['regra_legada_id'], legado.id)

    def test_api_buscar_nao_encontrada_404(self):
        r = self.client.get(
            self.url_buscar,
            {'ncm': '00000000', 'uf_origem': 'SP', 'uf_destino': 'RJ'},
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(r.json()['origem'], 'NAO_ENCONTRADA')

    def test_api_legado_buscar_intacta(self):
        RegraFiscal.objects.create(
            ncm='87654321',
            uf_origem='SP',
            uf_destino='MG',
            operacao='Saída',
            cfop='6102',
            aliquota_icms=12.0,
        )
        r = self.client.get(
            self.url_legado,
            {'ncm': '87654321', 'uf_origem': 'SP', 'uf_destino': 'MG', 'operacao': 'Saída'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['ncm'], '87654321')
