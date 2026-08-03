"""Emissão SEFAZ NF-e entrada própria — homologação e produção (mock transmissão)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.fiscal.models import ItemNFeEntrada, NFeEntrada, NFeNumeracaoConfiguracao
from apps.fiscal.nfe_emissao.retorno_sefaz import resultado_autorizacao_mock
from apps.fiscal.nfe_entrada_emissao.servico import emitir_nfe_entrada_homologacao
from apps.fiscal.nfe_entrada_emissao.servico_producao import emitir_nfe_entrada_producao
from apps.produtos.models import FamiliaProduto, Produto

User = get_user_model()

XML_AUTORIZADO_MOCK = (
    '<?xml version="1.0"?><retEnviNFe><cStat>104</cStat><xMotivo>Lote processado</xMotivo>'
    '<protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo>'
    '<nProt>135260000000001</nProt><chNFe>35260112345678000199550000000001001123456789</chNFe>'
    '</infProt></protNFe></retEnviNFe>'
)


def _empresa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emitente Entrada Emissao',
        cnpj='12345678000199',
        uf='SP',
        cidade='São Paulo',
        logradouro='Rua A',
        numero='1',
        bairro='Centro',
        cep='01001000',
        ie='123456789012',
    )


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'E{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod Entrada Emissao',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'EP-EM-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _rascunho_pronto(empresa: Empresa, cliente: Cliente, *, ambiente: str = 'homologacao') -> NFeEntrada:
    nf = NFeEntrada.objects.create(
        numero=f'EP-{uuid.uuid4().hex[:8]}',
        data=date.today(),
        tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        status_operacional=NFeEntrada.StatusOperacional.RASCUNHO,
        ambiente_emissao=ambiente,
        empresa_emitente=empresa,
        cliente_destinatario=cliente,
        fin_nfe='4',
        nat_op='Devolucao de mercadoria',
        chave_nfe_referenciada='35240112345678000199550010000000011123456789',
        valor_total=Decimal('100'),
    )
    prod = _produto()
    ItemNFeEntrada.objects.create(
        nf=nf,
        produto=prod,
        quantidade=Decimal('1'),
        valor=Decimal('100'),
        ncm='84818200',
        cfop='1202',
        unidade='PC',
        impostos_json={
            'icms': {'cst': '41', 'orig': '0'},
            'pis': {'cst': '07'},
            'cofins': {'cst': '07'},
        },
    )
    return nf


class NFeEntradaEmissaoSefazTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username='ep_emissao', password='x')
        self.empresa = _empresa()
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Dest Emissao',
            cnpj='98765432000188',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua C',
            numero='3',
            bairro='Centro',
            cep='01001000',
        )
        NFeNumeracaoConfiguracao.objects.create(
            empresa=self.empresa,
            modelo_documento='55',
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
            proximo_numero=900,
            ativo=True,
        )
        NFeNumeracaoConfiguracao.objects.create(
            empresa=self.empresa,
            modelo_documento='55',
            ambiente='producao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
            proximo_numero=50,
            ativo=True,
        )
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_api_criar_entrada_propria_emitida(self) -> None:
        prod = _produto()
        res = self.client_api.post(
            '/api/nf-entradas/criar-entrada-propria-emitida/',
            {
                'numero': 'EP-API-1',
                'data': date.today().isoformat(),
                'empresa_emitente_id': self.empresa.pk,
                'cliente_destinatario_id': self.cliente.pk,
                'fin_nfe': '4',
                'nat_op': 'Devolucao',
                'ambiente_emissao': 'homologacao',
                'itens': [
                    {
                        'produto_id': prod.pk,
                        'quantidade': '1',
                        'valor': '10.00',
                        'ncm': '84818200',
                        'cfop': '1202',
                        'unidade': 'PC',
                        'impostos_json': {
                            'icms': {'cst': '41', 'orig': '0'},
                            'pis': {'cst': '07'},
                            'cofins': {'cst': '07'},
                        },
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual(body['tipo_origem'], 'ENTRADA_PROPRIA_EMITIDA')
        self.assertEqual(body['status_operacional'], 'RASCUNHO')

    @patch('apps.fiscal.nfe_entrada_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_entrada_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_entrada_emissao.servico.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_entrada_emissao.servico.gerar_bytes_xml_oficial_nfe_entrada')
    def test_emitir_homologacao_autorizado(self, mock_xml, mock_assinar, mock_tx, _xsd) -> None:
        mock_xml.return_value = b'<NFe><infNFe Id="NFe1"><ide><tpAmb>2</tpAmb><tpNF>0</tpNF></ide></infNFe></NFe>'
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='Autorizado',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        nf = _rascunho_pronto(self.empresa, self.cliente)
        res = emitir_nfe_entrada_homologacao(nf, usuario=self.user)
        self.assertTrue(res['autorizado'])
        nf.refresh_from_db()
        self.assertEqual(nf.status_emissao_sefaz, 'AUTORIZADA_HOMOLOGACAO')
        self.assertEqual(nf.protocolo_autorizacao, '135260000000001')
        self.assertEqual(nf.numero_nfe, '000000900')
        cfg = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        )
        self.assertEqual(cfg.proximo_numero, 901)

    @patch('apps.fiscal.nfe_entrada_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_entrada_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_entrada_emissao.servico.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_entrada_emissao.servico.gerar_bytes_xml_oficial_nfe_entrada')
    def test_api_emitir_homologacao(self, mock_xml, mock_assinar, mock_tx, _xsd) -> None:
        mock_xml.return_value = b'<NFe><infNFe><ide><tpAmb>2</tpAmb></ide></infNFe></NFe>'
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='OK',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        nf = _rascunho_pronto(self.empresa, self.cliente)
        res = self.client_api.post(f'/api/nf-entradas/{nf.pk}/emitir-homologacao/', {}, format='json')
        self.assertIn(res.status_code, (200, 201), res.content)
        self.assertTrue(res.json().get('autorizado'))

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_integracao.adapters.certificado_a1.carregar_certificado_empresa')
    @patch('apps.fiscal.nfe_entrada_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_entrada_emissao.servico_producao.transmitir_nfe_producao')
    @patch('apps.fiscal.nfe_entrada_emissao.servico_producao.assinar_xml_nfe')
    @patch('apps.fiscal.nfe_entrada_emissao.servico_producao.gerar_bytes_xml_oficial_nfe_entrada')
    def test_emitir_producao_autorizado(
        self,
        mock_xml,
        mock_assinar,
        mock_tx,
        _xsd,
        mock_cert,
    ) -> None:
        mock_cert.return_value = object()
        mock_xml.return_value = b'<NFe><infNFe><ide><tpAmb>1</tpAmb><tpNF>0</tpNF></ide></infNFe></NFe>'
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='Autorizado',
            protocolo='135260000000099',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        nf = _rascunho_pronto(self.empresa, self.cliente, ambiente='producao')
        res = emitir_nfe_entrada_producao(
            nf,
            usuario=self.user,
            confirmacao_payload={
                'confirmar_emissao_producao': True,
                'confirmar_ambiente': 'PRODUCAO_SEFAZ',
            },
        )
        self.assertTrue(res['autorizado'])
        nf.refresh_from_db()
        self.assertEqual(nf.status_emissao_sefaz, 'AUTORIZADA_PRODUCAO')
        self.assertEqual(nf.ambiente_emissao, 'producao')
        self.assertEqual(nf.numero_nfe, '000000050')
