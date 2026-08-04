"""ERP 4.0.15.0 Parte 2B — XML oficial tpNF=0, preview e validação (sem SEFAZ)."""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.financeiro.models import TituloFinanceiro
from apps.fiscal.models import EstoqueCorrida, ItemNFeEntrada, NFeEntrada, NFeNumeracaoConfiguracao
from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe
from apps.fiscal.nfe_entrada_emissao.numeracao import reservar_numeracao_nfe_entrada
from apps.fiscal.nfe_entrada_emissao.validacao import validar_pre_emissao_homologacao_entrada
from apps.fiscal.nfe_entrada_emissao.xml_oficial import gerar_preview_xml_oficial_nfe_entrada
from apps.produtos.models import FamiliaProduto, Produto

User = get_user_model()

CHAVE_REF_44 = '35260612345678000199550010000000991000000099'

IMPOSTOS_ITEM_NT = {
    'icms': {'cst': '40', 'orig': '0'},
    'pis': {'cst': '49'},
    'cofins': {'cst': '49'},
}


def _xml_tag(xml: str, local: str) -> bool:
    return bool(re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(local)}\b', xml, re.IGNORECASE))


def _xml_val(xml: str, local: str) -> str | None:
    m = re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(local)}>([^<]+)</', xml, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _empresa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emitente Entrada 4015B',
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
        codigo_figura=f'B{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod Entrada 4015B',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'EP4015B-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _config_saida(empresa: Empresa, *, proximo: int = 200) -> NFeNumeracaoConfiguracao:
    """Sequência compartilhada com NF-e saída."""
    cfg, _ = NFeNumeracaoConfiguracao.objects.get_or_create(
        empresa=empresa,
        modelo_documento='55',
        ambiente=NFeNumeracaoConfiguracao.Ambiente.HOMOLOGACAO,
        tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
        serie='0',
        defaults={'proximo_numero': proximo, 'ativo': True},
    )
    if cfg.proximo_numero != proximo:
        cfg.proximo_numero = proximo
        cfg.save(update_fields=['proximo_numero'])
    return cfg


def _nf_pronta(
    empresa: Empresa,
    *,
    cliente: Cliente | None = None,
    fornecedor: Fornecedor | None = None,
    fin_nfe: str = '1',
    chave_ref: str = '',
    reservar: bool = True,
    user=None,
) -> NFeEntrada:
    nf = NFeEntrada.objects.create(
        numero=f'RASCUNHO-EPB-{uuid.uuid4().hex[:8]}',
        data=date.today(),
        tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        status_operacional=NFeEntrada.StatusOperacional.RASCUNHO,
        ambiente_emissao=NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
        empresa_emitente=empresa,
        cliente_destinatario=cliente,
        fornecedor=fornecedor,
        fin_nfe=fin_nfe,
        nat_op='Entrada de mercadoria',
        chave_nfe_referenciada=chave_ref,
        valor_total=Decimal('100'),
    )
    ItemNFeEntrada.objects.create(
        nf=nf,
        produto=_produto(),
        quantidade=Decimal('1'),
        valor=Decimal('100'),
        ncm='84818200',
        cfop='1102',
        unidade='PC',
        impostos_json=IMPOSTOS_ITEM_NT,
    )
    if reservar:
        _config_saida(empresa, proximo=300 + nf.pk % 100)
        reservar_numeracao_nfe_entrada(nf, usuario=user)
        nf.refresh_from_db()
    return nf


class NFeEntrada4015XmlPreviewTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username='ep4015b', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.empresa = _empresa()
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Dest 4015B',
            cnpj='98765432000188',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua C',
            numero='3',
            bairro='Centro',
            cep='01001000',
        )
        self.fornecedor = Fornecedor.objects.create(
            razao_social='Fornecedor Dest 4015B',
            cnpj='11111111000111',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua F',
            numero='4',
            bairro='Centro',
            cep='01001000',
        )

    def test_validacao_bloqueia_sem_emitente(self) -> None:
        nf = NFeEntrada.objects.create(
            numero='X',
            data=date.today(),
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
            ambiente_emissao=NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
            fin_nfe='1',
            nat_op='Teste',
            valor_total=Decimal('0'),
        )
        val = validar_pre_emissao_homologacao_entrada(nf)
        self.assertFalse(val['pronta'])
        self.assertTrue(any(p['codigo'] == 'EMITENTE_AUSENTE' for p in val['pendencias']))

    def test_validacao_bloqueia_sem_destinatario(self) -> None:
        nf = NFeEntrada.objects.create(
            numero='X',
            data=date.today(),
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
            ambiente_emissao=NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
            empresa_emitente=self.empresa,
            fin_nfe='1',
            nat_op='Teste',
            valor_total=Decimal('0'),
        )
        val = validar_pre_emissao_homologacao_entrada(nf)
        self.assertFalse(val['pronta'])
        self.assertTrue(any('DESTINATARIO' in p['codigo'] for p in val['pendencias']))

    def test_validacao_bloqueia_cliente_e_fornecedor(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, fornecedor=self.fornecedor, reservar=False)
        val = validar_pre_emissao_homologacao_entrada(nf)
        self.assertFalse(val['pronta'])
        self.assertTrue(any('DESTINATARIO' in p['codigo'] for p in val['pendencias']))

    def test_validacao_bloqueia_sem_fin_nfe(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, reservar=False)
        nf.fin_nfe = ''
        nf.save(update_fields=['fin_nfe'])
        val = validar_pre_emissao_homologacao_entrada(nf)
        self.assertTrue(any(p['codigo'] == 'FIN_NFE_AUSENTE' for p in val['pendencias']))

    def test_validacao_bloqueia_sem_item(self) -> None:
        nf = NFeEntrada.objects.create(
            numero='SEM-ITEM',
            data=date.today(),
            tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
            ambiente_emissao=NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
            empresa_emitente=self.empresa,
            cliente_destinatario=self.cliente,
            fin_nfe='1',
            nat_op='Teste',
            valor_total=Decimal('0'),
        )
        val = validar_pre_emissao_homologacao_entrada(nf)
        self.assertTrue(any('ITENS' in p['codigo'] for p in val['pendencias']))

    def test_validacao_bloqueia_item_sem_ncm_cfop_unidade(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, reservar=False)
        item = nf.itens.first()
        item.ncm = ''
        item.cfop = ''
        item.unidade = ''
        item.save()
        val = validar_pre_emissao_homologacao_entrada(nf)
        self.assertFalse(val['pronta'])

    def test_validacao_bloqueia_sem_numeracao_para_xml(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, reservar=False)
        val = validar_pre_emissao_homologacao_entrada(nf, exigir_numeracao=True)
        self.assertTrue(any(p['codigo'] == 'NUMERACAO_NAO_RESERVADA' for p in val['pendencias']))

    def test_reserva_entrada_consome_contador_saida(self) -> None:
        ensure_numeracao_padrao_nfe(self.empresa)
        cfg_saida = NFeNumeracaoConfiguracao.objects.get(
            empresa=self.empresa,
            ambiente='homologacao',
            tipo_operacao=NFeNumeracaoConfiguracao.TipoOperacao.SAIDA,
            serie='0',
        )
        prox_antes = cfg_saida.proximo_numero
        nf = _nf_pronta(self.empresa, cliente=self.cliente, reservar=False)
        reservar_numeracao_nfe_entrada(nf, usuario=self.user)
        nf.refresh_from_db()
        cfg_saida.refresh_from_db()
        self.assertEqual(cfg_saida.proximo_numero, prox_antes + 1)
        self.assertEqual(nf.numero_nfe, str(prox_antes).zfill(9))
        self.assertTrue(nf.chave_acesso)

    def test_preview_xml_tp_nf_zero(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        self.assertTrue(out['ok'])
        xml = out['xml']
        self.assertEqual(_xml_val(xml, 'tpNF'), '0')
        self.assertFalse(_xml_tag(xml, 'Signature'))

    def test_preview_xml_fin_nfe_do_registro(self) -> None:
        nf = _nf_pronta(self.empresa, fornecedor=self.fornecedor, fin_nfe='3', user=self.user)
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        self.assertEqual(_xml_val(out['xml'], 'finNFe'), '3')
        self.assertEqual(_xml_val(out['xml'], 'tPag'), '90')
        self.assertEqual(_xml_val(out['xml'], 'vPag'), '0.00')

    def test_preview_xml_sem_nfref_sem_chave(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, fin_nfe='1', user=self.user)
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        self.assertFalse(_xml_tag(out['xml'], 'NFref'))

    def test_preview_xml_com_nfref_fin4(self) -> None:
        nf = _nf_pronta(
            self.empresa,
            cliente=self.cliente,
            fin_nfe='4',
            chave_ref=CHAVE_REF_44,
            user=self.user,
        )
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        xml = out['xml']
        self.assertEqual(_xml_val(xml, 'finNFe'), '4')
        self.assertIn(CHAVE_REF_44, xml)
        self.assertEqual(_xml_val(xml, 'tPag'), '90')
        self.assertEqual(_xml_val(xml, 'vPag'), '0.00')

    def test_preview_xml_destinatario_cliente(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        self.assertIn('98765432000188', out['xml'])

    def test_preview_xml_destinatario_fornecedor(self) -> None:
        nf = _nf_pronta(self.empresa, fornecedor=self.fornecedor, user=self.user)
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        self.assertIn('11111111000111', out['xml'])

    def test_preview_nao_grava_protocolo_ou_autorizacao(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        gerar_preview_xml_oficial_nfe_entrada(nf)
        nf.refresh_from_db()
        self.assertFalse(nf.protocolo_autorizacao)
        self.assertFalse(nf.cstat_autorizacao)
        self.assertFalse(nf.autorizada_em)
        self.assertFalse(nf.xml_autorizado)

    def test_preview_nao_movimenta_estoque_nem_financeiro(self) -> None:
        estoque_antes = EstoqueCorrida.objects.count()
        fin_antes = TituloFinanceiro.objects.count()
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        gerar_preview_xml_oficial_nfe_entrada(nf)
        self.assertEqual(EstoqueCorrida.objects.count(), estoque_antes)
        self.assertEqual(TituloFinanceiro.objects.count(), fin_antes)

    def test_api_validar_emissao_homologacao(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, reservar=False)
        res = self.client.get(f'/api/nf-entradas/{nf.pk}/validar-emissao-homologacao/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['pronta'])

        nf.fin_nfe = ''
        nf.save(update_fields=['fin_nfe'])
        res2 = self.client.get(f'/api/nf-entradas/{nf.pk}/validar-emissao-homologacao/')
        self.assertEqual(res2.status_code, 409)
        self.assertFalse(res2.json()['pronta'])

    def test_api_preview_xml_oficial(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        res = self.client.get(f'/api/nf-entradas/{nf.pk}/preview-xml-oficial/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['tp_nf'], '0')
        self.assertIn('xml', res.json())

    def test_api_gerar_xml_persiste_sem_assinar(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        res = self.client.post(f'/api/nf-entradas/{nf.pk}/gerar-xml-oficial-emissao/')
        self.assertEqual(res.status_code, 200)
        nf.refresh_from_db()
        self.assertTrue(nf.xml_nfe_gerado)
        self.assertEqual(nf.status_emissao_sefaz, NFeEntrada.StatusEmissaoSefaz.XML_GERADO)
        self.assertFalse(_xml_tag(nf.xml_nfe_gerado, 'Signature'))

    def test_api_xml_gerado(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        self.client.post(f'/api/nf-entradas/{nf.pk}/gerar-xml-oficial-emissao/')
        res = self.client.get(f'/api/nf-entradas/{nf.pk}/xml-gerado/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['sem_autorizacao'])

    def test_preview_contem_cfop_ncm_item(self) -> None:
        nf = _nf_pronta(self.empresa, cliente=self.cliente, user=self.user)
        out = gerar_preview_xml_oficial_nfe_entrada(nf)
        xml = out['xml']
        self.assertEqual(_xml_val(xml, 'CFOP'), '1102')
        self.assertEqual(_xml_val(xml, 'NCM'), '84818200')
