"""NF-e 4.0.2 — emissão homologação SEFAZ (numeração, XML, assinatura, transmissão mock)."""

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
from django.test import TestCase
from lxml import etree
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, reservar_numeracao_nfe
from apps.fiscal.nfe_emissao.resposta import montar_resposta_emissao_homologacao
from apps.fiscal.nfe_emissao.validacao_util import extrair_mensagens_pendencias_validacao
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.fiscal.nfe_emissao.retorno_sefaz import parse_resposta_autorizacao_pynfe, resultado_autorizacao_mock
from apps.fiscal.nfe_emissao.servico import emitir_nfe_homologacao
from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao
from apps.fiscal.nfe_integracao.nfe_numero_fiscal_preliminar import resolver_numero_fiscal_preliminar
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao, validar_conferencia_nfe
from apps.produtos.models import FamiliaProduto, Produto


def _xml_tem_tag(xml: str, local: str) -> bool:
    """nfelib serializa com prefixo de namespace (ex.: ns0:emit)."""
    return bool(re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(local)}\b', xml, re.IGNORECASE))


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
    """Migração 0028 faz seed só das empresas existentes no migrate — testes criam empresa depois."""
    from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe

    ensure_numeracao_padrao_nfe(empresa)
    hom = NFeNumeracaoConfiguracao.objects.filter(
        empresa=empresa,
        ambiente='homologacao',
        serie='0',
    ).first()
    if hom and hom.proximo_numero < 2:
        hom.proximo_numero = 2
        hom.save(update_fields=['proximo_numero'])


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'N{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod NF 402',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'NF402-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_nf() -> tuple[PedidoVenda, ItemPedidoVenda, NFeSaida]:
    emp = Empresa.objects.create(
        razao_social='Emitente 402',
        cnpj='12345678000199',
        uf='SP',
        cidade='São Paulo',
        logradouro='Rua A',
        numero='1',
        bairro='Centro',
        cep='01001000',
        ie='123456789012',
        senha_certificado='test123',
    )
    pfx = _criar_pfx()
    with open(pfx, 'rb') as fh:
        emp.certificado_arquivo.save('t.pfx', fh, save=True)
    _ensure_numeracao_empresa(emp)

    cli = Cliente.objects.create(
        razao_social='Cliente 402',
        cnpj=_cnpj(),
        uf='RJ',
        cidade='Rio',
        logradouro='Rua B',
        numero='2',
        bairro='Centro',
        cep='20040002',
    )
    pedido = PedidoVenda.objects.create(
        numero=f'PV-402-{uuid.uuid4().hex[:4]}',
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
    return pedido, item, nf


def _preparar_pronta(nf: NFeSaida, user) -> NFeSaida:
    nf.refresh_from_db()
    validar_conferencia_nfe(nf, usuario=user)
    marcar_nfe_pronta_para_emissao(nf, usuario=user)
    nf.refresh_from_db()
    return nf


XML_AUTORIZADO_MOCK = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe35260512345678000199550090000000021000000021" versao="4.00"><ide><tpAmb>2</tpAmb></ide></infNFe></NFe>
<protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo><nProt>135260000000001</nProt></infProt></protNFe>
</nfeProc>"""


class NFe402EmissaoHomologacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe402', 'nfe402@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.pedido, self.item, self.nf = _pedido_nf()
        self.empresa = self.pedido.empresa_emitente
        self.nf.ind_final = '1'
        self.nf.ind_pres = '1'
        self.nf.indicadores_fiscais_confirmados = True
        self.nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
        self.nf = _preparar_pronta(self.nf, self.user)

    def test_seed_numeracao_homolog_e_producao(self):
        hom = NFeNumeracaoConfiguracao.objects.filter(
            empresa=self.empresa,
            ambiente='homologacao',
        ).first()
        prod = NFeNumeracaoConfiguracao.objects.filter(
            empresa=self.empresa,
            ambiente='producao',
        ).first()
        self.assertIsNotNone(hom)
        self.assertIsNotNone(prod)
        self.assertEqual(hom.serie, '0')
        self.assertEqual(prod.serie, '1')

    def test_sequencias_homolog_producao_separadas(self):
        hom = NFeNumeracaoConfiguracao.objects.get(empresa=self.empresa, ambiente='homologacao', serie='0')
        prod = NFeNumeracaoConfiguracao.objects.get(empresa=self.empresa, ambiente='producao', serie='1')
        hom.proximo_numero = 10
        hom.save(update_fields=['proximo_numero'])
        self.assertNotEqual(hom.proximo_numero, prod.proximo_numero)

    def test_reserva_usa_serie_homologacao(self):
        num = reservar_numeracao_nfe(self.nf, ambiente='homologacao', usuario=self.user)
        self.assertEqual(num.serie, '0')
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.serie_nfe, '0')

    def test_reserva_nao_usa_rascunho_fat(self):
        self.assertTrue('RASCUNHO' in (self.nf.numero or '').upper() or not self.nf.numero.isdigit())
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        self.assertNotIn('RASCUNHO', (self.nf.numero_nfe or '').upper())

    def test_reserva_nao_duplica(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        n1 = self.nf.numero_nfe
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.numero_nfe, n1)

    def test_chave_acesso_calculada(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        self.assertEqual(len(self.nf.chave_acesso), 44)
        self.assertTrue(self.nf.chave_acesso.isdigit())

    def test_xml_oficial_modelo_55(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        self.assertTrue(_xml_tem_tag(xml, 'mod'))
        self.assertIn('>55<', xml)

    def test_xml_nnf_numerico(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        m = re.search(r'<(?:[\w]+:)?nNF>(\d+)</', xml)
        self.assertIsNotNone(m)
        self.assertTrue(m.group(1).isdigit())

    def test_xml_serie_correta(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        ser = str(int(self.nf.serie_nfe))
        self.assertTrue(re.search(rf'<(?:[\w]+:)?serie>{ser}</', xml))

    def test_xml_oficial_com_itens_db_lista_nao_quebra_inf_cpl(self):
        """Regressão: xml_oficial passava list onde danfe_xml_adicionais esperava dict."""
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        self.assertIn('infNFe', xml)

    def test_xml_contem_emit_dest_prod_impostos_totais(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        for tag in ('emit', 'dest', 'det', 'imposto', 'total', 'ICMSTot'):
            self.assertTrue(_xml_tem_tag(xml, tag), msg=f'falta tag {tag}')

    def test_xml_sem_observacoes_internas(self):
        self.nf.observacoes_internas = 'SEGREDO INTERNO ERP'
        self.nf.save(update_fields=['observacoes_internas'])
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        xml = gerar_xml_oficial_emissao(self.nf).decode()
        self.assertNotIn('SEGREDO INTERNO', xml)

    @patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_emissao.servico.assinar_xml_nfe')
    def test_fluxo_emitir_homologacao_autorizado(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='Autorizado',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        antes_estoque = AtendimentoEstoque.objects.count()
        res = emitir_nfe_homologacao(self.nf, usuario=self.user)
        self.assertTrue(res['autorizado'])
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.protocolo_autorizacao, '135260000000001')
        self.assertEqual(self.nf.status_emissao_sefaz, 'AUTORIZADA_HOMOLOGACAO')
        self.assertFalse(self.nf.efeitos_autorizacao_aplicados_em)
        self.assertEqual(AtendimentoEstoque.objects.count(), antes_estoque)
        mock_tx.assert_called_once()
        self.assertEqual(mock_tx.call_args[0][0].ambiente_emissao, 'homologacao')

    @patch('apps.fiscal.nfe_emissao.transmissao.criar_comunicacao_sefaz')
    def test_transmissao_usa_homologacao(self, mock_criar):
        from apps.fiscal.nfe_emissao.transmissao import transmitir_nfe_homologacao

        mock_com = MagicMock()
        nfe_el = etree.Element('{http://www.portalfiscal.inf.br/nfe}NFe')
        mock_com.autorizacao.return_value = (1, MagicMock(text='<cStat>999</cStat>'), nfe_el)
        mock_criar.return_value = mock_com
        with patch('lxml.etree.fromstring', return_value=nfe_el):
            transmitir_nfe_homologacao(self.nf, b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"/>', self.empresa)
        mock_criar.assert_called_once()
        self.assertTrue(mock_criar.call_args.kwargs.get('homologacao'))

    def test_rejeicao_nao_marca_autorizada(self):
        parsed = parse_resposta_autorizacao_pynfe(1, '<retEnviNFe><cStat>225</cStat><xMotivo>Rejeicao</xMotivo></retEnviNFe>')
        self.assertFalse(parsed.autorizado)
        self.assertEqual(parsed.c_stat, '225')

    def test_parse_autorizado_salva_protocolo(self):
        root = etree.fromstring(XML_AUTORIZADO_MOCK.encode())
        parsed = parse_resposta_autorizacao_pynfe(0, root)
        self.assertTrue(parsed.autorizado)
        self.assertEqual(parsed.c_stat, '100')
        self.assertTrue(parsed.protocolo)

    def test_preliminar_usa_config_homolog(self):
        num = resolver_numero_fiscal_preliminar(self.nf)
        cfg = NFeNumeracaoConfiguracao.objects.get(empresa=self.empresa, ambiente='homologacao', serie='0')
        self.assertIn(num.serie, ('0', '000'))
        self.assertEqual(int(num.nnf), cfg.proximo_numero)

    def test_config_ausente_erro_amigavel(self):
        NFeNumeracaoConfiguracao.objects.filter(empresa=self.empresa).delete()
        with self.assertRaises(NFeNumeracaoError) as ctx:
            reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.assertIn('Configuração de numeração', str(ctx.exception))

    @patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_emissao.servico.assinar_xml_nfe')
    def test_api_emitir_homologacao(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='OK',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        url = f'/api/nf-saidas/{self.nf.pk}/emitir-homologacao/'
        res = self.client.post(url, {}, format='json')
        self.assertIn(res.status_code, (200, 201))
        body = res.json()
        self.assertTrue(body.get('ok'))
        self.assertTrue(body.get('autorizado'))
        self.assertEqual(body.get('ambiente'), 'homologacao')
        self.assertEqual(body.get('cstat'), '100')

    def test_api_patch_numeracao_homolog(self):
        hom = NFeNumeracaoConfiguracao.objects.get(empresa=self.empresa, ambiente='homologacao', serie='0')
        url = f'/api/nfe-numeracoes/{hom.pk}/'
        res = self.client.patch(url, {'serie': '900', 'proximo_numero': 2}, format='json')
        self.assertEqual(res.status_code, 400)
        res_ok = self.client.patch(url, {'serie': '0', 'proximo_numero': 2}, format='json')
        self.assertEqual(res_ok.status_code, 200)
        hom.refresh_from_db()
        self.assertEqual(hom.proximo_numero, 2)

    def test_conferencia_exibe_numeracao_homolog(self):
        payload = montar_conferencia_nfe_saida(self.nf)
        num = payload['emissao_sefaz'].get('numeracao_homologacao')
        self.assertIsNotNone(num)
        self.assertEqual(num['serie'], '0')

    def test_extrair_pendencias_de_grupos(self):
        val = validar_nfe_saida_para_emissao(self.nf)
        msgs = extrair_mensagens_pendencias_validacao(val)
        self.assertIsInstance(msgs, list)

    def test_resposta_padronizada_campos(self):
        res = montar_resposta_emissao_homologacao(
            self.nf,
            ok=True,
            autorizado=True,
            cstat='100',
            xmotivo='Autorizado',
            protocolo='123',
        )
        self.assertTrue(res['ok'])
        self.assertEqual(res['cstat'], '100')
        self.assertEqual(res['xmotivo'], 'Autorizado')

    @patch('apps.fiscal.nfe_emissao.servico.validar_emissao_completa', return_value={'ok': True, 'erros': []})
    @patch('apps.fiscal.nfe_emissao.servico.transmitir_nfe_homologacao')
    @patch('apps.fiscal.nfe_emissao.servico.assinar_xml_nfe')
    def test_emitir_incrementa_homolog_nao_producao(self, mock_assinar, mock_tx, _mock_xsd):
        mock_assinar.side_effect = lambda xml, emp, **kw: xml if isinstance(xml, bytes) else xml.encode()
        mock_tx.return_value = resultado_autorizacao_mock(
            autorizado=True,
            c_stat='100',
            x_motivo='OK',
            protocolo='135260000000001',
            xml_retorno=XML_AUTORIZADO_MOCK,
            xml_autorizado=XML_AUTORIZADO_MOCK,
        )
        hom = NFeNumeracaoConfiguracao.objects.get(empresa=self.empresa, ambiente='homologacao', serie='0')
        prod = NFeNumeracaoConfiguracao.objects.get(empresa=self.empresa, ambiente='producao', serie='1')
        prod_antes = prod.proximo_numero
        hom_antes = hom.proximo_numero
        emitir_nfe_homologacao(self.nf, usuario=self.user)
        hom.refresh_from_db()
        prod.refresh_from_db()
        self.assertGreater(hom.proximo_numero, hom_antes)
        self.assertEqual(prod.proximo_numero, prod_antes)

    def test_nao_gera_protocolo_fake_sem_sefaz(self):
        reservar_numeracao_nfe(self.nf, usuario=self.user)
        self.nf.refresh_from_db()
        self.assertEqual(self.nf.protocolo_autorizacao, '')

    def test_assinatura_modulo_nao_loga_senha_no_codigo(self):
        import inspect

        from apps.fiscal.nfe_emissao import assinatura as mod

        src = inspect.getsource(mod.assinar_xml_nfe)
        self.assertNotIn('senha_certificado', src.split('logger')[1] if 'logger' in src else src)
