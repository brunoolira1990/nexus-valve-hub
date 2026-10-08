"""Teste pontual — pedido de compra do cliente no XML/DANFE NF-e Saída."""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase

from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
    _nitemped_distinto_do_pedido,
    _resolver_linha_pedido_item,
    enriquecer_linhas_xml_nfe,
    inf_cpl_prioriza_pedido_para_danfe,
    montar_inf_ad_prod_item,
    montar_inf_cpl_nfe,
    resolver_xped_nitemped_item,
)


class _NfStub:
    pedido_cliente_numero = '123456'
    informacoes_adicionais = ''
    informacoes_fisco = ''
    cliente_id = None

    class _Itens:
        def all(self):
            return []

    itens = _Itens()


class _ItemStub:
    pedido_cliente_numero = ''
    pedido_cliente_item = '1'
    observacao_item = ''
    informacao_adicional_item = ''


class NFePedidoCompraClienteTests(SimpleTestCase):
    def test_nitemped_nao_repete_numero_pedido(self):
        self.assertEqual(_nitemped_distinto_do_pedido('55005050', '55005050'), '')
        self.assertEqual(_nitemped_distinto_do_pedido('55005050', '550050'), '')
        self.assertEqual(_nitemped_distinto_do_pedido('55005050', '10'), '10')

    def test_linha_item_usa_observacao_quando_campo_item_repete_pedido(self):
        linha = _resolver_linha_pedido_item('55005050', '55005050', observacao_item='01')
        self.assertEqual(linha, '01')

    def test_resolver_herda_pedido_cabecalho_para_xped(self):
        x_ped, n_item = resolver_xped_nitemped_item(
            _ItemStub(),
            {'pedido_cliente_item': '1'},
            pedido_cabecalho='123456',
        )
        self.assertEqual(x_ped, '123456')
        self.assertEqual(n_item, '1')

    def test_inf_ad_prod_formato_legivel(self):
        item = _ItemStub()
        item.observacao_item = '01'
        texto = montar_inf_ad_prod_item(
            _NfStub(),
            {'item_id': 1, 'pedido_cliente_numero': '123456', 'pedido_cliente_item': '1'},
            item,
        )
        self.assertEqual(texto, 'Pedido de compra: 123456 — Item: 1')

    def test_inf_ad_prod_caso_55005050_sem_repetir_pedido(self):
        item = _ItemStub()
        item.pedido_cliente_item = '55005050'
        item.observacao_item = '01'
        texto = montar_inf_ad_prod_item(
            _NfStub(),
            {
                'item_id': 10,
                'pedido_cliente_numero': '55005050',
                'pedido_cliente_item': '55005050',
                'observacao_item': '01',
            },
            item,
            pedido_cabecalho='55005050',
        )
        self.assertEqual(texto, 'Pedido de compra: 55005050 — Item: 01')

    def test_inf_cpl_prioriza_pedido_no_danfe(self):
        longo = 'X' * 400
        inf = f'{longo} PEDIDO DE COMPRA: 123456.'
        out = inf_cpl_prioriza_pedido_para_danfe(inf, max_len=420)
        self.assertIn('PEDIDO DE COMPRA: 123456', out)
        self.assertLessEqual(len(out), 420)

    def test_inf_cpl_pedido_compra_cliente(self):
        with mock.patch(
            'apps.fiscal.nfe_integracao.danfe_xml_adicionais._coletar_regras_fiscais_nfe',
            return_value=[],
        ):
            inf_cpl, _ = montar_inf_cpl_nfe(_NfStub(), {'itens': []})
        self.assertIn('PEDIDO DE COMPRA: 123456', inf_cpl)

    def test_enriquecer_linhas_preenche_xped_nitemped(self):
        nf = _NfStub()
        item = _ItemStub()
        item.pk = 10

        class _ItensMgr:
            def all(self_nonlocal):
                return [item]

        nf.itens = _ItensMgr()
        dados = {
            'itens': [
                {
                    'item_id': 10,
                    'pedido_cliente_numero': '',
                    'pedido_cliente_item': '1',
                    'snapshot_fiscal': {},
                },
            ],
        }
        enriquecer_linhas_xml_nfe(nf, dados)
        linha = dados['itens'][0]
        self.assertEqual(linha['x_ped'], '123456')
        self.assertEqual(linha['n_item_ped'], '1')
        self.assertIn('Pedido de compra: 123456', linha['inf_ad_prod'])

    def test_build_det_xml_tem_xped_nitemped(self):
        from apps.fiscal.nfe_saida_xml_nfelib import _build_det

        det = _build_det(
            {
                'n_item': 1,
                'item_id': 1,
                'c_prod': 'P1',
                'x_prod': 'Produto teste',
                'ncm': '84818095',
                'cfop': '5102',
                'u_com': 'UN',
                'q_com': Decimal('1'),
                'v_un_com': Decimal('5000'),
                'v_prod': Decimal('5000'),
                'x_ped': '123456',
                'n_item_ped': '1',
                'snapshot_fiscal': {'cst_icms': '20', 'base_icms': '2444.50', 'aliquota_icms': '18', 'valor_icms': '440.01'},
                'inf_ad_prod': 'Pedido de compra: 123456 — Item: 1',
            },
        )
        xml_frag = det.prod.xPed, det.prod.nItemPed, det.infAdProd
        self.assertEqual(xml_frag[0], '123456')
        self.assertEqual(xml_frag[1], '1')
        self.assertIn('Pedido de compra: 123456', xml_frag[2] or '')

    def test_build_det_resolve_pedido_cliente_sem_xped_na_linha(self):
        from apps.fiscal.nfe_saida_xml_nfelib import _build_det

        det = _build_det(
            {
                'n_item': 1,
                'item_id': 1,
                'c_prod': 'P1',
                'x_prod': 'Produto teste',
                'ncm': '84818095',
                'cfop': '5102',
                'u_com': 'UN',
                'q_com': Decimal('1'),
                'v_un_com': Decimal('5000'),
                'v_prod': Decimal('5000'),
                'pedido_cliente_numero': '4500074275',
                'pedido_cliente_item': '10',
                'snapshot_fiscal': {'cst_icms': '20', 'base_icms': '2444.50', 'aliquota_icms': '18', 'valor_icms': '440.01'},
            },
        )
        self.assertEqual(det.prod.xPed, '4500074275')
        self.assertEqual(det.prod.nItemPed, '10')

    def test_cache_preliminar_invalido_sem_tag_xped(self):
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import _xml_preliminar_cache_valido

        nf = _NfStub()
        nf.pedido_cliente_numero = '55005050'
        xml_so_infadprod = (
            '<NFe><infNFe><det nItem="1"><prod><xProd>P</xProd></prod>'
            '<infAdProd>Pedido de compra: 55005050 — Item: 01</infAdProd></det></infNFe></NFe>'
        )
        self.assertFalse(_xml_preliminar_cache_valido(nf, xml_so_infadprod))
        xml_com_tags = xml_so_infadprod.replace(
            '</prod>',
            '</prod><xPed>55005050</xPed><nItemPed>01</nItemPed>',
            1,
        )
        self.assertTrue(_xml_preliminar_cache_valido(nf, xml_com_tags))
