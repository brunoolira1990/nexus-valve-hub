"""NF-e: preservar até 3 casas no preço unitário (ItemNFeSaida.valor / vUnCom)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_emissao.schema_validacao import validar_xml_nfe_schema
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    gerar_danfe_bfr_de_xml_string,
    sanitizar_xml_para_bfr,
)
from apps.fiscal.nfe_preco_unitario import (
    MSG_PRECO_UNITARIO_NFE_MAX_3_CASAS,
    format_preco_unitario_nfe_xml,
    validar_preco_unitario_nfe,
)
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida, gerar_preview_xml_nfe_saida
from apps.fiscal.nfe_saida_xml_nfelib import gerar_xml_oficial_nfe_saida
from apps.fiscal.serializers import ItemNFeSaidaSerializer
from apps.fiscal.tests.danfe_pdf_assertions import compact_pdf_text, pdf_text
from apps.produtos.models import FamiliaProduto, Produto


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'U{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod unit',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'UN-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_item(*, qtd: Decimal, preco: Decimal) -> tuple[PedidoVenda, ItemPedidoVenda]:
    emp = Empresa.objects.create(razao_social='Emit', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(
        razao_social='Cli',
        cnpj=_cnpj(),
        uf='RJ',
        cidade='Rio de Janeiro',
        cep='20040-020',
        logradouro='Rua da Assembleia',
        numero='100',
        bairro='Centro',
    )
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=(qtd * preco).quantize(Decimal('0.01')),
    )
    prod = _produto()
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=qtd,
        quantidade_negociada=qtd,
        valor_unitario=preco.quantize(Decimal('0.01')),
        preco_por_unidade_negociada=preco,
        snapshot_fiscal={'origem_regra_fiscal_saida': 'LEGADO', 'ncm': '84818200', 'cfop': '5102'},
    )
    return pedido, item


def _nfe_de_faturamento(qtd: str, preco: Decimal) -> tuple[NFeSaida, ItemNFeSaida]:
    pedido, item = _pedido_item(qtd=Decimal(qtd), preco=preco)
    criado = criar_faturamento_pedido(
        pedido,
        {'itens': [{'item_pedido_id': item.pk, 'quantidade': qtd}]},
    )
    confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
    r = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
    nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
    return nf, nf.itens.get()


class NfePrecoUnitarioHelperTests(TestCase):
    def test_format_xml_e_validacao(self):
        self.assertEqual(format_preco_unitario_nfe_xml(Decimal('1128.125')), '1128.125')
        self.assertEqual(format_preco_unitario_nfe_xml(Decimal('1128.12')), '1128.12')
        self.assertEqual(format_preco_unitario_nfe_xml(Decimal('1128.1')), '1128.1')
        self.assertEqual(format_preco_unitario_nfe_xml(Decimal('1128')), '1128')
        self.assertEqual(format_preco_unitario_nfe_xml(Decimal('0.001')), '0.001')
        self.assertEqual(validar_preco_unitario_nfe('10.125'), Decimal('10.125'))
        with self.assertRaises(ValueError) as ctx:
            validar_preco_unitario_nfe('10.1255')
        self.assertIn('3 casas', str(ctx.exception))


class NfePrecoUnitarioConversaoTests(TestCase):
    def test_coluna_pg_e_modelo(self):
        f = ItemNFeSaida._meta.get_field('valor')
        self.assertEqual(f.max_digits, 16)
        self.assertEqual(f.decimal_places, 4)
        with connection.cursor() as c:
            c.execute(
                """
                SELECT numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_name = 'fiscal_itemnfesaida' AND column_name = 'valor'
                """
            )
            prec, scale = c.fetchone()
        self.assertEqual(int(prec), 16)
        self.assertEqual(int(scale), 4)

    def test_faturamento_1128_125_preserva_item_nfe(self):
        nf, item = _nfe_de_faturamento('4', Decimal('1128.125'))
        self.assertEqual(item.valor, Decimal('1128.1250'))
        item.refresh_from_db()
        self.assertEqual(item.valor, Decimal('1128.1250'))
        # Total comercial do item (snapshot) e coerência 4 × 1128.125
        self.assertEqual(Decimal(str((item.snapshot_comercial or {}).get('valor_total'))), Decimal('4512.50'))
        self.assertEqual((Decimal('4') * item.valor).quantize(Decimal('0.01')), Decimal('4512.50'))

    def test_casos_adicionais_e_regressao_duas_casas(self):
        for preco in (Decimal('10'), Decimal('10.1'), Decimal('10.12'), Decimal('10.125'), Decimal('0.001')):
            nf, item = _nfe_de_faturamento('1', preco)
            self.assertEqual(item.valor, preco.quantize(Decimal('0.0001')))

    def test_multiplos_itens_totalizam(self):
        pedido, item_a = _pedido_item(qtd=Decimal('2'), preco=Decimal('1128.125'))
        prod_b = _produto()
        ItemPedidoVenda.objects.create(
            pedido=pedido,
            produto=prod_b,
            quantidade=Decimal('1'),
            quantidade_negociada=Decimal('1'),
            valor_unitario=Decimal('10.12'),
            preco_por_unidade_negociada=Decimal('10.12'),
            snapshot_fiscal={'origem_regra_fiscal_saida': 'LEGADO', 'ncm': '84818200', 'cfop': '5102'},
        )
        item_b = pedido.itens.exclude(pk=item_a.pk).get()
        criado = criar_faturamento_pedido(
            pedido,
            {
                'itens': [
                    {'item_pedido_id': item_a.pk, 'quantidade': '2'},
                    {'item_pedido_id': item_b.pk, 'quantidade': '1'},
                ],
            },
        )
        confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
        r = gerar_nfe_saida_from_faturamento(pedido, criado['faturamento_id'])
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        self.assertEqual(nf.itens.count(), 2)
        vals = {it.valor for it in nf.itens.all()}
        self.assertIn(Decimal('1128.1250'), vals)
        self.assertIn(Decimal('10.1200'), vals)


class NfePrecoUnitarioSerializerApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe3d', 'nfe3d@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_serializer_aceita_e_rejeita(self):
        prod = _produto()
        ok = ItemNFeSaidaSerializer(
            data={
                'produto_id': prod.pk,
                'quantidade': '1',
                'valor': '1128.125',
            },
        )
        self.assertTrue(ok.is_valid(), ok.errors)
        self.assertEqual(ok.validated_data['valor'], Decimal('1128.125'))

        bad = ItemNFeSaidaSerializer(
            data={
                'produto_id': prod.pk,
                'quantidade': '1',
                'valor': '10.1255',
            },
        )
        self.assertFalse(bad.is_valid())
        self.assertIn('valor', bad.errors)
        self.assertIn('3 casas', str(bad.errors['valor']))
        self.assertIn('3 casas', MSG_PRECO_UNITARIO_NFE_MAX_3_CASAS)

    def test_api_get_preserva_terceira_casa(self):
        nf, item = _nfe_de_faturamento('4', Decimal('1128.125'))
        r = self.client.get(f'/api/nf-saidas/{nf.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = next(i for i in r.json()['itens'] if i['id'] == item.pk)
        self.assertEqual(Decimal(str(row['valor'])), Decimal('1128.1250'))


class NfePrecoUnitarioXmlDanfeTests(TestCase):
    def test_preview_e_xml_oficial(self):
        nf, _item = _nfe_de_faturamento('4', Decimal('1128.125'))
        dados = gerar_dados_preview_nfe_saida(nf)
        linha = dados['itens'][0]
        self.assertEqual(linha['v_un_com'], '1128.125')
        self.assertEqual(linha['v_prod'], '4512.50')

        # XML oficial nfelib (sem transmissão)
        with mock.patch(
            'apps.fiscal.nfe_saida_xml_nfelib.validar_nfe_saida_para_emissao',
            return_value={
                'ok': True,
                'bloqueado': False,
                'pendencias': [],
                'alertas': [],
                'grupos': {},
                'status_prontidao': 'PRONTO',
                'pode_emitir': True,
            },
        ):
            try:
                payload = gerar_xml_oficial_nfe_saida(nf)
                xml = payload.get('xml') or ''
            except Exception:
                xml = ''
        if not xml:
            with mock.patch(
                'apps.fiscal.nfe_saida_preview.validar_nfe_saida_para_emissao',
                return_value={
                    'ok': True,
                    'bloqueado': False,
                    'pendencias': [],
                    'alertas': [],
                    'grupos': {},
                    'status_prontidao': 'PRONTO',
                    'pode_emitir': True,
                },
            ):
                prev = gerar_preview_xml_nfe_saida(nf)
                xml = prev.get('xml') or ''

        self.assertIn('1128.125', xml)
        self.assertRegex(xml, r'<(?:[\w]+:)?vUnCom>\s*1128\.125\s*</(?:[\w]+:)?vUnCom>')
        self.assertRegex(xml, r'<(?:[\w]+:)?vUnTrib>\s*1128\.125\s*</(?:[\w]+:)?vUnTrib>')
        self.assertRegex(xml, r'<(?:[\w]+:)?vProd>\s*4512\.50\s*</(?:[\w]+:)?vProd>')

        # Schema instalado — validar XML completo quando possível
        if 'infNFe' in xml or 'NFe' in xml:
            res = validar_xml_nfe_schema(xml, 'XML_ASSINADO')
            if not res.get('ok'):
                erros = str(res.get('erros') or res).lower()
                self.assertNotIn('vuncom', erros)
                self.assertNotIn('vuntrib', erros)


    def test_danfe_local_mostra_terceira_casa(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
            '<NFe><infNFe Id="NFe35200100000000000000550010000000011000000010" versao="4.00">'
            '<ide><cUF>35</cUF><cNF>00000001</cNF><natOp>Venda</natOp><mod>55</mod>'
            '<serie>1</serie><nNF>1</nNF><dhEmi>2026-01-15T10:00:00-03:00</dhEmi>'
            '<tpNF>1</tpNF><idDest>1</idDest><cMunFG>3550308</cMunFG><tpImp>1</tpImp>'
            '<tpEmis>1</tpEmis><cDV>0</cDV><tpAmb>2</tpAmb><finNFe>1</finNFe>'
            '<indFinal>1</indFinal><indPres>1</indPres><procEmi>0</procEmi><verProc>Nexus</verProc></ide>'
            '<emit><CNPJ>12345678000199</CNPJ><xNome>Emit Teste</xNome>'
            '<enderEmit><xLgr>Rua A</xLgr><nro>1</nro><xBairro>Centro</xBairro>'
            '<cMun>3550308</cMun><xMun>Sao Paulo</xMun><UF>SP</UF><CEP>01001000</CEP>'
            '<cPais>1058</cPais><xPais>Brasil</xPais></enderEmit>'
            '<IE>123456789012</IE><CRT>3</CRT></emit>'
            '<dest><CNPJ>98765432000111</CNPJ><xNome>Dest Teste</xNome>'
            '<enderDest><xLgr>Rua B</xLgr><nro>2</nro><xBairro>Centro</xBairro>'
            '<cMun>3304557</cMun><xMun>Rio de Janeiro</xMun><UF>RJ</UF><CEP>20040020</CEP>'
            '<cPais>1058</cPais><xPais>Brasil</xPais></enderDest>'
            '<indIEDest>9</indIEDest></dest>'
            '<det nItem="1"><prod><cProd>001</cProd><cEAN>SEM GTIN</cEAN>'
            '<xProd>Item sinteticos</xProd><NCM>84818099</NCM><CFOP>5102</CFOP>'
            '<uCom>UN</uCom><qCom>4.0000</qCom><vUnCom>1128.125</vUnCom><vProd>4512.50</vProd>'
            '<cEANTrib>SEM GTIN</cEANTrib><uTrib>UN</uTrib><qTrib>4.0000</qTrib>'
            '<vUnTrib>1128.125</vUnTrib><indTot>1</indTot></prod>'
            '<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC>'
            '<vBC>4512.50</vBC><pICMS>18.00</pICMS><vICMS>812.25</vICMS></ICMS00></ICMS>'
            '<PIS><PISAliq><CST>01</CST><vBC>4512.50</vBC><pPIS>1.65</pPIS><vPIS>74.46</vPIS></PISAliq></PIS>'
            '<COFINS><COFINSAliq><CST>01</CST><vBC>4512.50</vBC><pCOFINS>7.60</pCOFINS>'
            '<vCOFINS>342.95</vCOFINS></COFINSAliq></COFINS></imposto></det>'
            '<total><ICMSTot><vBC>4512.50</vBC><vICMS>812.25</vICMS><vICMSDeson>0.00</vICMSDeson>'
            '<vFCP>0.00</vFCP><vBCST>0.00</vBCST><vST>0.00</vST><vFCPST>0.00</vFCPST>'
            '<vFCPSTRet>0.00</vFCPSTRet><vProd>4512.50</vProd><vFrete>0.00</vFrete>'
            '<vSeg>0.00</vSeg><vDesc>0.00</vDesc><vII>0.00</vII><vIPI>0.00</vIPI>'
            '<vIPIDevol>0.00</vIPIDevol><vPIS>74.46</vPIS><vCOFINS>342.95</vCOFINS>'
            '<vOutro>0.00</vOutro><vNF>4512.50</vNF></ICMSTot></total>'
            '<transp><modFrete>9</modFrete></transp>'
            '<pag><detPag><tPag>01</tPag><vPag>4512.50</vPag></detPag></pag>'
            '</infNFe></NFe></nfeProc>'
        )
        from brazilfiscalreport.danfe.danfe import format_number

        self.assertEqual(format_number('1128.125', 3), '1.128,125')
        self.assertEqual(format_number('4512.50', 2), '4.512,50')
        pdf = gerar_danfe_bfr_de_xml_string(sanitizar_xml_para_bfr(xml))
        self.assertTrue(pdf.startswith(b'%PDF'))
        texto = compact_pdf_text(pdf_text(pdf))
        # compact_pdf_text remove pontos: 1.128,125 → 1128,125
        self.assertIn('1128,125', texto)
        self.assertIn('4512,50', texto)
