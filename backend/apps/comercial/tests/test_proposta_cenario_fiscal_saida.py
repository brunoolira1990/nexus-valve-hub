"""Fase Saída 3.3 — ativação por proposta do cenário fiscal de saída."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import ItemProposta, Proposta
from apps.comercial.serializers import ItemPropostaSerializer, PropostaSerializer
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida
from apps.regras_fiscais.base_pis_cofins_saida import percentual_saida_total_com_deducao_icms
from apps.regras_fiscais.saida_fiscal import (
    comparar_regra_fiscal_saida_legado_cenario,
    deve_usar_cenario_fiscal_saida,
    find_regra_fiscal_saida_com_fallback,
    resolve_usar_cenario_fiscal_para_proposta,
)
from apps.comercial import pricing as price_rules


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto(ncm: str = '84818200') -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'P{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'P-{suf}',
        unidade='PC',
        ncm=ncm,
    )


def _proposta(*, usar_cenario: bool = False, cenario=None) -> Proposta:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), uf='RJ')
    hoje = date.today()
    return Proposta.objects.create(
        numero=f'PROP-{uuid.uuid4().hex[:6]}',
        data=hoje,
        validade=hoje + timedelta(days=30),
        empresa_emitente=emp,
        cliente=cli,
        uf_origem='SP',
        usar_cenario_fiscal_saida=usar_cenario,
        cenario_fiscal_saida=cenario,
    )


class PropostaCenarioFiscalModelTests(TestCase):
    def test_nova_proposta_modelo_manual_legado_preservado(self):
        """Criação direta no modelo ainda permite legado (compatibilidade histórica)."""
        p = _proposta()
        self.assertFalse(p.usar_cenario_fiscal_saida)
        self.assertIsNone(p.cenario_fiscal_saida_id)

    def test_resolve_usar_cenario_opt_in(self):
        p = _proposta(usar_cenario=True)
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False):
            self.assertTrue(deve_usar_cenario_fiscal_saida(p))
            self.assertTrue(resolve_usar_cenario_fiscal_para_proposta(p))

    @override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
    def test_flag_global_forca_cenario(self):
        p = _proposta(usar_cenario=False)
        self.assertTrue(resolve_usar_cenario_fiscal_para_proposta(p))


class PropostaCenarioFiscalMotorTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()
        self.escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818200',
        )
        RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='6102',
            tipo_operacao='VENDA',
            cst_icms='00',
            aliquota_icms=Decimal('18'),
        )
        RegraFiscal.objects.create(
            ncm='84818200',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )

    def test_proposta_legado_usa_tabela_antiga(self):
        p = _proposta(usar_cenario=False)
        prod = _produto('84818200')
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False):
            r = find_regra_fiscal_saida_com_fallback(
                '84818200',
                'SP',
                'RJ',
                'Saída',
                usar_cenario=resolve_usar_cenario_fiscal_para_proposta(p),
            )
        self.assertEqual(r['origem'], 'LEGADO')
        self.assertEqual(r['aliquota_icms'], '12.00')

    def test_proposta_cenario_usa_regra_saida(self):
        p = _proposta(usar_cenario=True)
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False):
            r = find_regra_fiscal_saida_com_fallback(
                '84818200',
                'SP',
                'RJ',
                'Saída',
                usar_cenario=resolve_usar_cenario_fiscal_para_proposta(p),
            )
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')
        self.assertEqual(r['aliquota_icms'], '18.00')

    def test_fallback_legado_quando_cenario_sem_regra(self):
        RegraFiscal.objects.create(
            ncm='84818201',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )
        p = _proposta(usar_cenario=True)
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False):
            r = find_regra_fiscal_saida_com_fallback(
                '84818201',
                'SP',
                'RJ',
                'Saída',
                usar_cenario=resolve_usar_cenario_fiscal_para_proposta(p),
            )
        self.assertEqual(r['origem'], 'LEGADO')

    def test_cenario_especifico_na_proposta(self):
        outro = garantir_cenario_saida_padrao()
        # criar segundo cenário não-padrao seria ideal; usar cenario padrao com regra única NCM
        p = _proposta(usar_cenario=True, cenario=self.cenario)
        with override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False):
            r = find_regra_fiscal_saida_com_fallback(
                '84818200',
                'SP',
                'RJ',
                'Saída',
                usar_cenario=True,
                cenario_id=p.cenario_fiscal_saida_id,
            )
        self.assertEqual(r['origem'], 'CENARIO_SAIDA')


class PropostaCenarioFiscalSerializerTests(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818210',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            aliquota_icms=Decimal('18'),
        )
        RegraFiscal.objects.create(
            ncm='84818210',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=18.0,
        )

    def test_item_expoe_origem_fiscal(self):
        p = _proposta(usar_cenario=True, cenario=self.cenario)
        prod = _produto('84818210')
        item = ItemProposta.objects.create(
            proposta=p,
            produto=prod,
            quantidade=Decimal('1'),
            valor_unitario=Decimal('100'),
        )
        item = ItemProposta.objects.select_related('proposta', 'proposta__cenario_fiscal_saida', 'produto').get(
            pk=item.pk,
        )
        ser = ItemPropostaSerializer(item, context={'proposta_incoming': {'usar_cenario_fiscal_saida': True}})
        data = ser.data
        self.assertEqual(data['origem_regra_fiscal_saida'], 'CENARIO_SAIDA')
        self.assertIsNotNone(data['regra_fiscal_saida_id'])

    def test_proposta_antiga_inalterada_apos_migration(self):
        p = Proposta.objects.filter(usar_cenario_fiscal_saida=False).first()
        if p is None:
            p = _proposta(usar_cenario=False)
        self.assertFalse(p.usar_cenario_fiscal_saida)

    def test_opt_in_aplica_deducao_icms_base_pis_cofins(self):
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818211',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            aliquota_icms=Decimal('18'),
            aliquota_pis=Decimal('1.65'),
            aliquota_cofins=Decimal('7.6'),
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=True,
        )
        p = _proposta(usar_cenario=True, cenario=self.cenario)
        prod = _produto('84818211')
        ser = ItemPropostaSerializer(
            data={
                'produto_id': prod.pk,
                'quantidade': '1',
                'valor_unitario': '100',
                'custo_utilizado': '60',
                'modo_preco': 'sugerido',
            },
            context={'proposta_incoming': {'usar_cenario_fiscal_saida': True, 'cenario_fiscal_saida_id': self.cenario.pk}},
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pct_sem, _ = percentual_saida_total_com_deducao_icms(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            origem='CENARIO_SAIDA',
            deduzir_icms_base_pis=False,
            deduzir_icms_base_cofins=False,
        )
        pct_com, _ = percentual_saida_total_com_deducao_icms(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            origem='CENARIO_SAIDA',
            deduzir_icms_base_pis=True,
            deduzir_icms_base_cofins=True,
        )
        self.assertGreater(pct_sem, pct_com)
        pct_legado = price_rules.percentual_saida_total(
            Decimal('18'),
            Decimal('1.65'),
            Decimal('7.6'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
        )
        self.assertEqual(pct_legado, pct_sem)


class PropostaCenarioFiscalAPITests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user('prop_cf', 'prop@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_patch_usar_cenario(self):
        p = _proposta(usar_cenario=False)
        prod = _produto('84818220')
        r = self.client.patch(
            f'/api/propostas/{p.pk}/',
            {
                'usar_cenario_fiscal_saida': True,
                'itens': [
                    {
                        'produto_id': prod.pk,
                        'quantidade': '1',
                        'valor_unitario': '100',
                        'custo_utilizado': '50',
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['usar_cenario_fiscal_saida'])
        item = body['itens'][0]
        self.assertIn(item['origem_regra_fiscal_saida'], ('CENARIO_SAIDA', 'LEGADO', 'NAO_ENCONTRADA'))


class PropostaCenarioFiscalIntegracaoTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user('prop_cf2', 'prop2@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.cenario = garantir_cenario_saida_padrao()
        escopo = CenarioFiscalSaidaEscopo.objects.create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            ncm='84818230',
        )
        RegraFiscalSaida.objects.create(
            escopo=escopo,
            cenario=self.cenario,
            ativo=True,
            uf_origem='SP',
            uf_destino='RJ',
            cfop_venda='5102',
            aliquota_icms=Decimal('18'),
        )
        RegraFiscal.objects.create(
            ncm='84818230',
            uf_origem='SP',
            uf_destino='RJ',
            operacao='Saída',
            cfop='5102',
            aliquota_icms=12.0,
        )

    def test_comparativo_continua_funcionando(self):
        cmp = comparar_regra_fiscal_saida_legado_cenario(
            ncm='84818230',
            uf_origem='SP',
            uf_destino='RJ',
        )
        self.assertIn(cmp['status'], ('IGUAL', 'DIVERGENTE', 'CENARIO_NAO_ENCONTRADO', 'LEGADO_NAO_ENCONTRADO'))

    def test_endpoint_legado_buscar_continua_funcionando(self):
        url = reverse('regrafiscal-buscar')
        r = self.client.get(
            url,
            {'ncm': '84818230', 'uf_origem': 'SP', 'uf_destino': 'RJ', 'operacao': 'Saída'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['aliquota_icms'], 12.0)
