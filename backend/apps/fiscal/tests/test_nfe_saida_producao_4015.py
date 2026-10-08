"""NF-e 4.0.15.x Fase 3B — emissão produção SEFAZ (flag, guards, SEFAZ mockada)."""

from __future__ import annotations

import re
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from lxml import etree
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.config_producao import (
    CONFIRMACAO_AMBIENTE_PRODUCAO,
    MSG_PRODUCAO_NAO_HABILITADA,
)
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.retorno_sefaz import resultado_autorizacao_mock
from apps.fiscal.nfe_emissao.servico import emitir_nfe_homologacao
from apps.fiscal.nfe_emissao.servico_producao import emitir_nfe_producao
from apps.fiscal.nfe_emissao.transmissao_producao import (
    NFeTransmissaoProducaoError,
    re_tpamb_homolog,
    re_tpamb_prod,
    transmitir_nfe_producao,
)
from apps.fiscal.nfe_emissao.validacao_producao import montar_validacao_emissao_producao
from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao, validar_conferencia_nfe
from apps.fiscal.tests.nfe_4015_test_support import NFe4015GruposMixin, vincular_grupo_teste
from apps.financeiro.models import TituloFinanceiro
from apps.produtos.models import FamiliaProduto, Produto

CONFIRMACAO_PRODUCAO = {
    'confirmar_emissao_producao': True,
    'confirmar_ambiente': CONFIRMACAO_AMBIENTE_PRODUCAO,
}

XML_AUTORIZADO_MOCK_PROD = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe35260512345678000199550010000000011000000011" versao="4.00"><ide><tpAmb>1</tpAmb></ide></infNFe></NFe>
<protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo><nProt>135260000000099</nProt></infProt></protNFe>
</nfeProc>"""


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _criar_pfx(senha: str = 'test123') -> str:
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Empresa Teste')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pfx = pkcs12.serialize_key_and_certificates(
        name=b't',
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(senha.encode()),
    )
    tmp = tempfile.NamedTemporaryFile(suffix='.pfx', delete=False)
    tmp.write(pfx)
    tmp.flush()
    tmp.close()
    return tmp.name


def _ensure_numeracao_empresa(empresa: Empresa) -> None:
    from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe

    ensure_numeracao_padrao_nfe(empresa)
    hom = NFeNumeracaoConfiguracao.objects.filter(
        empresa=empresa,
        ambiente='homologacao',
        tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        serie='0',
    ).first()
    if hom and hom.proximo_numero < 2:
        hom.proximo_numero = 2
        hom.save(update_fields=['proximo_numero'])


def _produto() -> Produto:
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
        descricao='Prod NF 4015 prod',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'NF4015P-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_nf() -> tuple[PedidoVenda, NFeSaida]:
    emp = Empresa.objects.create(
        razao_social='Emitente 4015 prod',
        cnpj='12345678000199',
        uf='SP',
        cidade='São Paulo',
        logradouro='Rua A',
        numero='1',
        bairro='Centro',
        cep='01001000',
        ie='123456789012',
        senha_certificado='test123',
        nfe_ambiente=Empresa.NfeAmbiente.PRODUCAO,
    )
    pfx = _criar_pfx()
    with open(pfx, 'rb') as fh:
        emp.certificado_arquivo.save('t.pfx', fh, save=True)
    _ensure_numeracao_empresa(emp)

    cli = Cliente.objects.create(
        razao_social='Cliente 4015 prod',
        cnpj=_cnpj(),
        uf='RJ',
        cidade='Rio de Janeiro',
        logradouro='Rua B',
        numero='2',
        bairro='Centro',
        cep='20040002',
    )
    pedido = PedidoVenda.objects.create(
        numero=f'PV-4015P-{uuid.uuid4().hex[:4]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=Decimal('400'),
    )
    prod = _produto()
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('4'),
        quantidade_negociada=Decimal('4'),
        valor_unitario=Decimal('100'),
        preco_por_unidade_negociada=Decimal('100'),
        snapshot_fiscal={
            'origem_regra_fiscal_saida': 'LEGADO',
            'ncm': '84818200',
            'cfop': '5102',
            'icms': {'cst_icms': '00', 'base': '400', 'aliquota': '18', 'valor': '72'},
            'pis': {'cst': '08'},
            'cofins': {'cst': '08'},
        },
    )
    criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '4'}]})
    confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
    fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
    return pedido, nf


def _preparar_pronta(nf: NFeSaida, user) -> NFeSaida:
    nf.refresh_from_db()
    validar_conferencia_nfe(nf, usuario=user)
    marcar_nfe_pronta_para_emissao(nf, usuario=user)
    nf.refresh_from_db()
    return nf


def _grant_permissao_producao(user) -> None:
    vincular_grupo_teste(user, 'admin')


def _preparar_nf_indicadores(nf: NFeSaida) -> NFeSaida:
    nf.ind_final = '1'
    nf.ind_pres = '1'
    nf.indicadores_fiscais_confirmados = True
    nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
    return nf


class NFe4015ProducaoSefazTests(NFe4015GruposMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe4015p', 'nfe4015p@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.nf = _pedido_nf()
        self.empresa = self.pedido.empresa_emitente
        self.nf = _preparar_nf_indicadores(self.nf)
        _grant_permissao_producao(self.user)
        self.nf = _preparar_pronta(self.nf, self.user)

    def test_flag_default_desligada(self):
        from django.conf import settings

        self.assertFalse(getattr(settings, 'NFE_PRODUCAO_HABILITADA', False))

    def test_endpoint_emitir_producao_bloqueia_sem_flag(self):
        url = f'/api/nf-saidas/{self.nf.pk}/emitir-producao/'
        resp = self.client.post(url, CONFIRMACAO_PRODUCAO, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(resp.json()['ok'])
        self.assertIn('não habilitada', resp.json()['mensagem'].lower())

    def test_endpoint_exige_confirmacao_explicita(self):
        with override_settings(NFE_PRODUCAO_HABILITADA=True):
            url = f'/api/nf-saidas/{self.nf.pk}/emitir-producao/'
            resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Confirmação explícita', resp.json()['mensagem'])

    def test_endpoint_bloqueia_usuario_fiscal_sem_permissao(self):
        fiscal = get_user_model().objects.create_user('fiscal4015', 'f4015@test.com', 'x')
        vincular_grupo_teste(fiscal, 'fiscal')
        self.client.force_authenticate(fiscal)
        with override_settings(NFE_PRODUCAO_HABILITADA=True):
            url = f'/api/nf-saidas/{self.nf.pk}/emitir-producao/'
            resp = self.client.post(url, CONFIRMACAO_PRODUCAO, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('permissão', resp.json()['mensagem'].lower())
        self.client.force_authenticate(self.user)

    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    def test_transmissao_nao_chama_sefaz_sem_flag(self, mock_tx):
        url = f'/api/nf-saidas/{self.nf.pk}/emitir-producao/'
        self.client.post(url, CONFIRMACAO_PRODUCAO, format='json')
        mock_tx.assert_not_called()

    def test_reserva_producao_bloqueada_sem_flag(self):
        with self.assertRaises(NFeNumeracaoError) as ctx:
            reservar_numeracao_nfe(self.nf, ambiente='producao', usuario=self.user)
        self.assertIn('não habilitada', str(ctx.exception).lower())

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_reserva_producao_nao_altera_homologacao(self):
        hom = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
        )
        prod = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='producao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='1',
        )
        hom_antes = hom.proximo_numero
        prod_antes = prod.proximo_numero
        num = reservar_numeracao_nfe(self.nf, ambiente='producao', usuario=self.user)
        hom.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual(num.serie, '1')
        self.assertEqual(hom.proximo_numero, hom_antes)
        self.assertGreater(prod.proximo_numero, prod_antes)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.ambiente_emissao, 'producao')

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_validar_xml_local_producao_aceita_tpamb_1(self):
        from apps.fiscal.nfe_emissao.validacao import validar_xml_emissao_local

        reservar_numeracao_nfe(self.nf, ambiente='producao', usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        erros = validar_xml_emissao_local(xml, nfe_saida=self.nf)
        self.assertFalse(any('tpAmb deve ser 2' in e for e in erros), erros)

    def test_validar_xml_local_homolog_rejeita_tpamb_1(self):
        from apps.fiscal.nfe_emissao.validacao import validar_xml_emissao_local

        self.nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
        self.nf.save(update_fields=['ambiente_emissao'])
        xml = '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe35260512345678000199550010000000011000000011" versao="4.00"><ide><mod>55</mod><serie>0</serie><nNF>1</nNF><tpAmb>1</tpAmb></ide></infNFe></NFe>'
        erros = validar_xml_emissao_local(xml, nfe_saida=self.nf)
        self.assertTrue(any('tpAmb deve ser 2' in e for e in erros))

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_xml_producao_tpamb_1(self):
        reservar_numeracao_nfe(self.nf, ambiente='producao', usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        self.assertTrue(re_tpamb_prod(xml))
        self.assertFalse(re_tpamb_homolog(xml))

    def test_transmissao_producao_rejeita_tpamb_2(self):
        with override_settings(NFE_PRODUCAO_HABILITADA=True):
            reservar_numeracao_nfe(self.nf, ambiente='producao', usuario=self.user)
            self.nf.refresh_from_db()
            xml_homolog = '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe><ide><tpAmb>2</tpAmb></ide></infNFe></NFe>'
            with self.assertRaises(NFeTransmissaoProducaoError) as ctx:
                transmitir_nfe_producao(self.nf, xml_homolog, self.empresa)
            self.assertIn('tpAmb=1', str(ctx.exception))

    def test_transmissao_producao_rejeita_nf_homologacao(self):
        self.nf.ambiente_emissao = NFeSaida.AmbienteEmissao.HOMOLOGACAO
        self.nf.save(update_fields=['ambiente_emissao'])
        with override_settings(NFE_PRODUCAO_HABILITADA=True):
            xml_prod = '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe><ide><tpAmb>1</tpAmb></ide></infNFe></NFe>'
            with self.assertRaises(NFeTransmissaoProducaoError):
                transmitir_nfe_producao(self.nf, xml_prod, self.empresa)

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_validacao_producao_readonly(self):
        payload = montar_validacao_emissao_producao(self.nf)
        self.assertTrue(payload['producao_habilitada'])
        self.assertTrue(payload['pronta'])
        self.assertEqual(payload['pendencias'], [])

    @override_settings(NFE_PRODUCAO_HABILITADA=False)
    def test_validacao_producao_pendencia_flag(self):
        payload = montar_validacao_emissao_producao(self.nf)
        self.assertFalse(payload['pronta'])
        self.assertTrue(any('não habilitada' in p['mensagem'].lower() for p in payload['pendencias']))

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    def test_fluxo_emitir_producao_autorizado_mock(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='Autorizado',
            protocolo='135260000000099',
            xml_retorno=XML_AUTORIZADO_MOCK_PROD,
            xml_autorizado=XML_AUTORIZADO_MOCK_PROD,
        )
        antes_estoque = AtendimentoEstoque.objects.count()
        self.assertFalse((self.nf.xml_autorizado or '').strip())
        res = emitir_nfe_producao(
            self.nf,
            usuario=self.user,
            confirmacao_payload=CONFIRMACAO_PRODUCAO,
        )
        self.assertTrue(res['autorizado'])
        self.assertEqual(res['ambiente'], 'producao')
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, 'AUTORIZADA_PRODUCAO')
        self.assertEqual(self.nf.protocolo_autorizacao, '135260000000099')
        self.assertTrue((self.nf.xml_autorizado or '').strip())
        self.assertEqual(AtendimentoEstoque.objects.count(), antes_estoque)
        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_SAIDA,
                origem_id=self.nf.pk,
            ).count(),
            1,
        )
        self.assertIn('financeiro', res)
        self.assertTrue(res['financeiro'].get('gerado') or res['financeiro'].get('ja_existente'))
        mock_tx.assert_called_once()
        self.assertEqual(mock_tx.call_args[0][0].ambiente_emissao, 'producao')

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    def test_danfe_producao_autorizada_usa_xml_protocolado(self):
        from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import brazil_fiscal_report_disponivel
        from apps.fiscal.nfe_saida_danfe_autorizado import gerar_danfe_autorizado_nfe_saida
        from apps.fiscal.danfe_render import DanfeBfrRenderError
        from apps.fiscal.nfe_saida_preview import gerar_preview_danfe_nfe_saida

        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
        self.nf.status = 'AUTORIZADA_PRODUCAO'
        self.nf.ambiente_emissao = NFeSaida.AmbienteEmissao.PRODUCAO
        self.nf.serie_nfe = '1'
        self.nf.numero_nfe = '000000361'
        self.nf.protocolo_autorizacao = '135260000000099'
        self.nf.chave_acesso = '35260512345678000199550010000000036100000036'
        self.nf.xml_autorizado = XML_AUTORIZADO_MOCK_PROD
        self.nf.save()
        with self.assertRaises(DanfeBfrRenderError) as ctx_preview:
            gerar_preview_danfe_nfe_saida(self.nf)
        self.assertIn('danfe-autorizado', str(ctx_preview.exception).lower())
        pdf, meta = gerar_danfe_autorizado_nfe_saida(self.nf)
        if brazil_fiscal_report_disponivel():
            self.assertFalse(meta.get('conferencia'))
            self.assertFalse(meta.get('bloqueado'), meta.get('mensagens'))
            self.assertEqual(meta.get('danfe_origem'), 'xml_autorizado_procNFe')
            self.assertEqual(meta.get('tp_amb'), '1')
            self.assertIsNone(meta.get('marca_dagua'))
            self.assertGreater(len(pdf), 100)

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.servico_producao.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico_producao.transmitir_nfe_producao')
    @patch('apps.fiscal.nfe_emissao.servico_producao.assinar_xml_nfe')
    def test_rejeicao_mock_nao_marca_autorizada_producao(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=False,
            c_stat='539',
            x_motivo='Rejeição teste produção',
            protocolo='',
            xml_retorno='<retEnviNFe><cStat>104</cStat></retEnviNFe>',
            xml_autorizado='',
        )
        res = emitir_nfe_producao(
            self.nf,
            usuario=self.user,
            confirmacao_payload=CONFIRMACAO_PRODUCAO,
        )
        self.assertFalse(res['autorizado'])
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, 'REJEITADA_PRODUCAO')
        self.assertFalse((self.nf.xml_autorizado or '').strip())

    @override_settings(NFE_PRODUCAO_HABILITADA=True)
    @patch('apps.fiscal.nfe_emissao.transmissao_producao.parse_resposta_autorizacao_pynfe')
    @patch('apps.fiscal.nfe_emissao.transmissao_producao.criar_comunicacao_sefaz')
    def test_transmissao_producao_usa_ambiente_producao_pynfe(self, mock_criar, mock_parse):
        reservar_numeracao_nfe(self.nf, ambiente='producao', usuario=self.user)
        self.nf.refresh_from_db()
        mock_com = MagicMock()
        nfe_el = etree.Element('{http://www.portalfiscal.inf.br/nfe}NFe')
        mock_com.autorizacao.return_value = (1, MagicMock(text='<cStat>999</cStat>'), nfe_el)
        mock_criar.return_value = mock_com
        mock_parse.return_value = resultado_autorizacao_mock(autorizado=False, c_stat='999')
        xml_prod = b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe><ide><tpAmb>1</tpAmb></ide></infNFe></NFe>'
        with patch('lxml.etree.fromstring', return_value=nfe_el):
            transmitir_nfe_producao(self.nf, xml_prod, self.empresa)
        mock_criar.assert_called_once()
        self.assertFalse(mock_criar.call_args.kwargs.get('homologacao'))

    @patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_emissao.servico.assinar_xml_nfe')
    def test_homologacao_regressao_continua_funcionando(self, mock_assinar, mock_tx, _mock_xsd):
        from apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao import XML_AUTORIZADO_MOCK

        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        res = emitir_nfe_homologacao(self.nf, usuario=self.user)
        self.assertTrue(res['autorizado'])
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.status_emissao_sefaz, 'AUTORIZADA_HOMOLOGACAO')
        self.assertEqual(self.nf.ambiente_emissao, 'homologacao')
        mock_tx.assert_called_once()

    def test_mensagem_bloqueio_padrao(self):
        self.assertEqual(MSG_PRODUCAO_NAO_HABILITADA, 'Emissão NF-e produção não habilitada.')
