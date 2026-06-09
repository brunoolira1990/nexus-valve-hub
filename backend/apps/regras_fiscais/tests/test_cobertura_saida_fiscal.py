"""Fase Saída 3.2 — cobertura / homologação em lote do cenário fiscal de saída."""

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
from apps.comercial.pricing import find_regra_fiscal_saida_com_fallback
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida
from apps.regras_fiscais.saida_fiscal import cobertura_propostas_fiscal_saida


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(ncm: str = '84818095') -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'FC{suf}',
        descricao_base='Fam cobertura',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod cobertura',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'COB-{suf}',
        unidade='PC',
        ncm=ncm,
    )


def _proposta_com_item(
    *,
    ncm: str = '84818095',
    numero: str = 'PROP-COB-1',
    ufo: str = 'SP',
    ufd: str = 'RJ',
) -> tuple[Proposta, ItemProposta]:
    emp = Empresa.objects.create(razao_social='Emit Cob', cnpj=_cnpj(), uf=ufo)
    cli = Cliente.objects.create(razao_social='Cli Cob', cnpj=_cnpj(), uf=ufd)
    hoje = date.today()
    prop = Proposta.objects.create(
        numero=numero,
        data=hoje,
        validade=hoje + timedelta(days=30),
        empresa_emitente=emp,
        cliente=cli,
        uf_origem=ufo,
        status='Pendente',
    )
    prod = _produto(ncm)
    item = ItemProposta.objects.create(
        proposta=prop,
        produto=prod,
        quantidade=Decimal('1'),
        valor_unitario=Decimal('100'),
    )
    return prop, item


def _escopo_ncm(cenario, ncm: str) -> CenarioFiscalSaidaEscopo:
    return CenarioFiscalSaidaEscopo.objects.create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
    )


def _regra_saida(escopo, **kwargs) -> RegraFiscalSaida:
    defaults = {
        'ativo': True,
        'uf_origem': 'SP',
        'uf_destino': 'RJ',
        'cfop_venda': '5102',
        'tipo_operacao': 'VENDA',
        'cst_icms': '00',
        'aliquota_icms': Decimal('18'),
        'cst_ipi': '50',
        'aliquota_ipi': Decimal('5'),
        'cst_pis': '01',
        'aliquota_pis': Decimal('1.65'),
        'cst_cofins': '01',
        'aliquota_cofins': Decimal('7.6'),
    }
    defaults.update(kwargs)
    return RegraFiscalSaida.objects.create(escopo=escopo, cenario=escopo.cenario, **defaults)


class CoberturaPropostasFiscalTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()

    def test_painel_igual(self):
        escopo = _escopo_ncm(self.cenario, '84818095')
        _regra_saida(escopo)
        RegraFiscal.objects.create(
            ncm='84818095',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            cst_icms='00',
            aliquota_icms=18.0,
            cst_ipi='50',
            aliquota_ipi=5.0,
            cst_pis='01',
            aliquota_pis=1.65,
            cst_cofins='01',
            aliquota_cofins=7.6,
        )
        _proposta_com_item()
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
            limite=50,
        )
        self.assertEqual(r['resumo']['iguais'], 1)
        self.assertEqual(r['itens'][0]['status'], 'IGUAL')

    def test_painel_divergente(self):
        escopo = _escopo_ncm(self.cenario, '84818096')
        _regra_saida(escopo, aliquota_icms=Decimal('18'))
        RegraFiscal.objects.create(
            ncm='84818096',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        _proposta_com_item(ncm='84818096', numero='PROP-COB-2')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
        )
        self.assertEqual(r['resumo']['divergentes'], 1)
        self.assertEqual(r['itens'][0]['status'], 'DIVERGENTE')

    def test_cenario_nao_encontrado(self):
        RegraFiscal.objects.create(
            ncm='84818097',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        _proposta_com_item(ncm='84818097', numero='PROP-COB-3')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
        )
        self.assertEqual(r['resumo']['cenario_nao_encontrado'], 1)

    def test_legado_nao_encontrado(self):
        escopo = _escopo_ncm(self.cenario, '84818098')
        _regra_saida(escopo)
        _proposta_com_item(ncm='84818098', numero='PROP-COB-4')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
        )
        self.assertEqual(r['resumo']['legado_nao_encontrado'], 1)

    def test_ambos_nao_encontrados(self):
        _proposta_com_item(ncm='84818099', numero='PROP-COB-5')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
        )
        self.assertEqual(r['resumo']['ambos_nao_encontrados'], 1)

    def test_lacunas_agrupam_ncm_uf(self):
        RegraFiscal.objects.create(
            ncm='84818110',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        _proposta_com_item(ncm='84818110', numero='PROP-COB-6A')
        _proposta_com_item(ncm='84818110', numero='PROP-COB-6B')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
            max_scan=100,
        )
        self.assertTrue(r['lacunas'])
        lac = next(x for x in r['lacunas'] if x['ncm'] == '84818110')
        self.assertEqual(lac['quantidade_itens'], 2)
        self.assertEqual(lac['status_predominante'], 'CENARIO_NAO_ENCONTRADO')

    def test_filtro_somente_divergentes(self):
        escopo = _escopo_ncm(self.cenario, '84818111')
        _regra_saida(escopo, aliquota_icms=Decimal('18'))
        RegraFiscal.objects.create(
            ncm='84818111',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        escopo2 = _escopo_ncm(self.cenario, '84818112')
        _regra_saida(escopo2)
        RegraFiscal.objects.create(
            ncm='84818112',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            cst_icms='00',
            aliquota_icms=18.0,
            cst_ipi='50',
            aliquota_ipi=5.0,
            cst_pis='01',
            aliquota_pis=1.65,
            cst_cofins='01',
            aliquota_cofins=7.6,
        )
        _proposta_com_item(ncm='84818111', numero='PROP-COB-7A')
        _proposta_com_item(ncm='84818112', numero='PROP-COB-7B')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
            somente_divergentes=True,
            max_scan=100,
        )
        self.assertEqual(len(r['itens']), 1)
        self.assertEqual(r['itens'][0]['status'], 'DIVERGENTE')
        self.assertEqual(r['resumo']['divergentes'], 1)
        self.assertEqual(r['resumo']['iguais'], 1)

    def test_filtro_somente_sem_cenario(self):
        RegraFiscal.objects.create(
            ncm='84818113',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        escopo = _escopo_ncm(self.cenario, '84818114')
        _regra_saida(escopo)
        RegraFiscal.objects.create(
            ncm='84818114',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=18.0,
        )
        _proposta_com_item(ncm='84818113', numero='PROP-COB-8A')
        _proposta_com_item(ncm='84818114', numero='PROP-COB-8B')
        r = cobertura_propostas_fiscal_saida(
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
            somente_sem_cenario=True,
            max_scan=100,
        )
        self.assertEqual(len(r['itens']), 1)
        self.assertEqual(r['itens'][0]['status'], 'CENARIO_NAO_ENCONTRADO')

    def test_read_only_nao_altera_proposta(self):
        prop, item = _proposta_com_item(numero='PROP-COB-9')
        custo_antes = item.custo_utilizado
        numero_antes = prop.numero
        cobertura_propostas_fiscal_saida(
            proposta_id=prop.pk,
            data_inicial=date.today() - timedelta(days=1),
            data_final=date.today(),
        )
        item.refresh_from_db()
        prop.refresh_from_db()
        self.assertEqual(item.custo_utilizado, custo_antes)
        self.assertEqual(prop.numero, numero_antes)

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
    def test_flag_desligada_mantem_legado(self):
        escopo = _escopo_ncm(self.cenario, '84818115')
        _regra_saida(escopo)
        _proposta_com_item(ncm='84818115', numero='PROP-COB-10')
        fb = find_regra_fiscal_saida_com_fallback('84818115', 'SP', 'RJ', 'Saída')
        self.assertEqual(fb['origem'], 'NAO_ENCONTRADA')


class CoberturaPropostasAPITests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('cob_api', 'cob@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.url = reverse('regrafiscal-saida-cobertura-propostas')
        self.cenario = garantir_cenario_saida_padrao()

    def test_endpoint_200_divergente(self):
        escopo = _escopo_ncm(self.cenario, '84818120')
        _regra_saida(escopo, cfop_venda='6102', aliquota_icms=Decimal('18'))
        RegraFiscal.objects.create(
            ncm='84818120',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        _proposta_com_item(ncm='84818120', numero='PROP-API-1')
        r = self.client.get(
            self.url,
            {
                'data_inicial': (date.today() - timedelta(days=1)).isoformat(),
                'data_final': date.today().isoformat(),
            },
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        self.assertEqual(body['resumo']['divergentes'], 1)
        self.assertTrue(body['itens'][0]['divergencias'])

    def test_endpoint_200_sem_itens(self):
        r = self.client.get(
            self.url,
            {
                'data_inicial': '2099-01-01',
                'data_final': '2099-12-31',
            },
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['resumo']['total_itens'], 0)
