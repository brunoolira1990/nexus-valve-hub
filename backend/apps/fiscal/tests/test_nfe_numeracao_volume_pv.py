"""NF-e — numeração compacta de volumes a partir do Pedido de Venda (ERP 4.0.14.x)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_numeracao_volume_pv import (
    compactar_numero_pedido_venda,
    sugerir_numeracao_volumes_pedido,
)
from apps.fiscal.nfe_saida_efeitos import aplicar_efeitos_autorizacao_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_transp_bindings import aplicar_transp_nfelib, montar_transporte_dados_nfe
from apps.fiscal.serializers import NFeSaidaSerializer
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item


class CompactarNumeroPedidoVendaTests(TestCase):
    def test_exemplo_aprovado(self):
        self.assertEqual(compactar_numero_pedido_venda('PV-20260714-0042'), '260714-0042')

    def test_virada_de_mes_e_zeros(self):
        self.assertEqual(compactar_numero_pedido_venda('PV-20260101-0001'), '260101-0001')
        self.assertEqual(compactar_numero_pedido_venda('PV-20261231-0999'), '261231-0999')

    def test_bissexto_valido(self):
        self.assertEqual(compactar_numero_pedido_venda('PV-20240229-0001'), '240229-0001')

    def test_bissexto_invalido_2026(self):
        self.assertIsNone(compactar_numero_pedido_venda('PV-20260229-0001'))

    def test_data_invalida(self):
        self.assertIsNone(compactar_numero_pedido_venda('PV-20261301-0001'))
        self.assertIsNone(compactar_numero_pedido_venda('PV-20260230-0001'))

    def test_legados_e_incompletos(self):
        self.assertIsNone(compactar_numero_pedido_venda('4368'))
        self.assertIsNone(compactar_numero_pedido_venda('PV-20260714-42'))
        self.assertIsNone(compactar_numero_pedido_venda('PV20260714-0042'))
        self.assertIsNone(compactar_numero_pedido_venda('pv-20260714-0042'))
        self.assertIsNone(compactar_numero_pedido_venda('PV-20260714-00421'))
        self.assertIsNone(compactar_numero_pedido_venda(''))
        self.assertIsNone(compactar_numero_pedido_venda(None))
        self.assertIsNone(compactar_numero_pedido_venda('  '))

    def test_sugerir_so_se_vazio(self):
        self.assertEqual(
            sugerir_numeracao_volumes_pedido('PV-20260714-0042', ''),
            '260714-0042',
        )
        self.assertIsNone(sugerir_numeracao_volumes_pedido('PV-20260714-0042', 'MANUAL-1'))
        self.assertIsNone(sugerir_numeracao_volumes_pedido('4368', ''))


class NumeracaoVolumesCreateRascunhoTests(TestCase):
    def test_rascunho_novo_recebe_sugestao(self):
        pedido, item = _pedido_item()
        pedido.numero = 'PV-20260714-0042'
        pedido.save(update_fields=['numero'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        self.assertEqual(nf.numeracao_volumes, '260714-0042')
        self.assertEqual(nf.status, 'RASCUNHO')

    def test_pedido_legado_nao_inventa_valor(self):
        pedido, item = _pedido_item()
        pedido.numero = '4368'
        pedido.save(update_fields=['numero'])
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        self.assertEqual(nf.numeracao_volumes, '')

    def test_preserva_valor_manual_e_retry_idempotente(self):
        pedido, item = _pedido_item()
        pedido.numero = 'PV-20260714-0042'
        pedido.save(update_fields=['numero'])
        fat = _faturamento_pronto(pedido, item)
        r1 = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r1['nfe_saida_id'])
        self.assertEqual(nf.numeracao_volumes, '260714-0042')

        nf.numeracao_volumes = 'VOL-MANUAL-99'
        nf.save(update_fields=['numeracao_volumes'])

        r2 = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        self.assertTrue(r2['ja_existia'])
        self.assertEqual(r2['nfe_saida_id'], nf.pk)
        nf.refresh_from_db()
        self.assertEqual(nf.numeracao_volumes, 'VOL-MANUAL-99')

    def test_faturamento_parcial_mesma_referencia(self):
        pedido, item = _pedido_item(qtd=Decimal('10'), preco=Decimal('100'))
        pedido.numero = 'PV-20260315-0007'
        pedido.save(update_fields=['numero'])

        fat1 = _faturamento_pronto(pedido, item, qtd='4')
        r1 = gerar_nfe_saida_from_faturamento(pedido, fat1.pk)
        nf1 = NFeSaida.objects.get(pk=r1['nfe_saida_id'])

        fat2_criado = criar_faturamento_pedido(
            pedido,
            {'itens': [{'item_pedido_id': item.pk, 'quantidade': '3'}]},
        )
        confirmar_faturamento_pedido(pedido, fat2_criado['faturamento_id'])
        fat2 = FaturamentoPedidoVenda.objects.get(pk=fat2_criado['faturamento_id'])
        r2 = gerar_nfe_saida_from_faturamento(pedido, fat2.pk)
        nf2 = NFeSaida.objects.get(pk=r2['nfe_saida_id'])

        self.assertNotEqual(nf1.pk, nf2.pk)
        self.assertEqual(nf1.numeracao_volumes, '260315-0007')
        self.assertEqual(nf2.numeracao_volumes, '260315-0007')


class NumeracaoVolumesXmlDanfeTests(TestCase):
    def test_xml_nvol_recebe_valor_persistido(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        pedido, item = _pedido_item(qtd=Decimal('1'), preco=Decimal('100'))
        pedido.numero = 'PV-20260714-0042'
        pedido.save(update_fields=['numero'])
        fat = _faturamento_pronto(pedido, item, qtd='1')
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        self.assertEqual(nf.numeracao_volumes, '260714-0042')

        nf.modalidade_frete = '0'
        nf.quantidade_volumes = 1
        nf.especie_volumes = 'VOLUME'
        nf.peso_bruto = Decimal('10')
        nf.peso_liquido = Decimal('9')
        nf.save()

        dados = montar_transporte_dados_nfe(nf)
        self.assertEqual(dados['numeracao_volumes'], '260714-0042')

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(inf, nfe, dados)
        self.assertEqual(inf.transp.vol[0].nVol, '260714-0042')

    def test_mod_frete_9_omite_grupo_vol(self):
        from nfelib.nfe.bindings import v4_0 as nfe

        inf = nfe.Tnfe.InfNfe()
        aplicar_transp_nfelib(
            inf,
            nfe,
            {
                'mod_frete': '9',
                'quantidade_volumes': 1,
                'especie_volumes': 'VOLUME',
                'numeracao_volumes': '260714-0042',
                'peso_bruto': '10.000',
                'peso_liquido': '9.000',
            },
        )
        self.assertEqual(inf.transp.modFrete, '9')
        self.assertFalse(getattr(inf.transp, 'vol', None))

    def test_danfe_bfr_exibe_nvol_do_xml(self):
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
            XML_NFE_EXEMPLO_POC,
            gerar_danfe_bfr_de_xml_string,
        )
        from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text

        # POC usa modFrete=9 (sem vol). Inclui nVol com modFrete≠9 para o BFR ler o XML.
        xml = XML_NFE_EXEMPLO_POC.replace(
            '<transp><modFrete>9</modFrete></transp>',
            (
                '<transp><modFrete>0</modFrete>'
                '<vol><qVol>1</qVol><esp>VOLUME</esp><nVol>260714-0042</nVol>'
                '<pesoB>1.000</pesoB><pesoL>1.000</pesoL></vol></transp>'
            ),
            1,
        )
        pdf = gerar_danfe_bfr_de_xml_string(xml)
        # BFR exibe nVol; compact_pdf_text remove hífen → 2607140042.
        texto = compact_pdf_text(pdf_text(pdf))
        self.assertIn('2607140042', texto)
        self.assertIn('NUMERACAO', texto)

    def test_autorizada_bloqueia_alteracao_numeracao(self):
        user = get_user_model().objects.create_user('nv_pv', 'nv_pv@test.com', 'x')
        pedido, item = _pedido_item()
        pedido.numero = 'PV-20260714-0042'
        pedido.save(update_fields=['numero'])
        fat = _faturamento_pronto(pedido, item)
        nf = NFeSaida.objects.get(pk=gerar_nfe_saida_from_faturamento(pedido, fat.pk)['nfe_saida_id'])
        self.assertEqual(nf.numeracao_volumes, '260714-0042')

        aplicar_efeitos_autorizacao_nfe_saida(nf, usuario=user)
        nf.refresh_from_db()
        ser = NFeSaidaSerializer(
            nf,
            data={'numeracao_volumes': 'ALTERADO'},
            partial=True,
        )
        self.assertFalse(ser.is_valid())
        nf.refresh_from_db()
        self.assertEqual(nf.numeracao_volumes, '260714-0042')
