"""XML/DANFE — grupo transp com volumes e transportadora completa."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cadastros.models import Transportadora
from apps.fiscal.nfe_transp_bindings import aplicar_transp_nfelib, montar_transporte_dados_nfe
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.tests.test_nfe_saida_354_danfe_conferencia import _regra


class NfeTranspBindingsTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user('transp1', 't1@test.com', 'x')
        _regra()

    def test_montar_transporte_dados_nfe(self):
        pedido, item = _pedido_item(qtd=Decimal('1'), preco=Decimal('100'))
        transp = Transportadora.objects.create(
            razao_social='WINNER EXPRESS TRANSPORTES LTDA',
            cnpj='32241095000121',
            ie='1234567890',
            logradouro='Rua Teste',
            numero='100',
            bairro='Centro',
            cidade='São Paulo',
            uf='SP',
            cep='01001000',
        )
        from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
        from apps.fiscal.models import NFeSaida

        item.snapshot_fiscal = {'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00'}
        item.save(update_fields=['snapshot_fiscal'])
        fat = _faturamento_pronto(pedido, item, qtd='1')
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        nf.transportadora = transp
        nf.quantidade_volumes = 1
        nf.especie_volumes = 'VOLUME'
        nf.numeracao_volumes = '4040'
        nf.peso_bruto = Decimal('500')
        nf.peso_liquido = Decimal('500')
        nf.save()

        dados = montar_transporte_dados_nfe(nf)
        self.assertEqual(dados['quantidade_volumes'], 1)
        self.assertEqual(dados['especie_volumes'], 'VOLUME')
        self.assertEqual(dados['numeracao_volumes'], '4040')
        self.assertEqual(dados['peso_bruto'], '500.00')
        self.assertEqual(dados['transportadora_ender'], 'Rua Teste 100')
        self.assertNotIn('Centro', dados['transportadora_ender'])
        self.assertIn('32241095000121', dados['transportadora_cnpj'])

    def test_aplicar_transp_nfelib_mod9_omite_transporta_e_vol(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(
            inf,
            nfe,
            {
                'mod_frete': '9',
                'transportadora_nome': 'WINNER EXPRESS TRANSPORTES LTDA',
                'transportadora_cnpj': '32241095000121',
                'transportadora_ie': '1234567890',
                'transportadora_ender': 'Rua Teste 100',
                'transportadora_mun': 'São Paulo',
                'transportadora_uf': 'SP',
                'quantidade_volumes': 1,
                'especie_volumes': 'VOLUME',
                'numeracao_volumes': '4040',
                'peso_bruto': '500.000',
                'peso_liquido': '500.000',
            },
        )
        self.assertEqual(inf.transp.modFrete, '9')
        self.assertIsNone(getattr(inf.transp, 'transporta', None))
        self.assertFalse(getattr(inf.transp, 'vol', None))

    def test_totais_nfelib_serializam_frete_e_total_uma_vez(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        from apps.fiscal.nfe_emissao.xml_serializacao import build_icms_tot_bindings

        totais = build_icms_tot_bindings(
            nfe,
            {
                'v_prod': '250.00',
                'v_desc': '5.00',
                'v_frete': '12.34',
                'v_nf': '257.34',
            },
        )
        self.assertEqual(str(totais.vFrete), '12.34')
        self.assertEqual(str(totais.vNF), '257.34')

    def test_aplicar_transp_nfelib_vol_e_transporta(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(
            inf,
            nfe,
            {
                'mod_frete': '0',
                'transportadora_nome': 'WINNER EXPRESS TRANSPORTES LTDA',
                'transportadora_cnpj': '32241095000121',
                'transportadora_ie': '1234567890',
                'transportadora_ender': 'Rua Teste 100',
                'transportadora_mun': 'São Paulo',
                'transportadora_uf': 'SP',
                'quantidade_volumes': 1,
                'especie_volumes': 'VOLUME',
                'numeracao_volumes': '4040',
                'peso_bruto': '500.000',
                'peso_liquido': '500.000',
            },
        )
        self.assertEqual(inf.transp.modFrete, '0')
        self.assertEqual(inf.transp.transporta.CNPJ, '32241095000121')
        self.assertEqual(inf.transp.vol[0].qVol, '1')
        self.assertEqual(inf.transp.vol[0].esp, 'VOLUME')
        self.assertEqual(inf.transp.vol[0].nVol, '4040')
        self.assertEqual(str(inf.transp.vol[0].pesoB), '500.000')
        self.assertEqual(str(inf.transp.vol[0].pesoL), '500.000')
