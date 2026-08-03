"""Gera rascunho de entrada própria a partir de NF-e Saída autorizada."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.fiscal.models import ItemNFeEntrada, ItemNFeSaida, NFeEntrada, NFeSaida
from apps.fiscal.nfe_entrada_from_saida_devolucao import (
    cfop_entrada_devolucao_from_saida,
    gerar_entrada_devolucao_from_nfe_saida,
)
from apps.produtos.models import FamiliaProduto, Produto

User = get_user_model()


def _empresa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emitente Devolucao',
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
        codigo_figura=f'D{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod Devolucao',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'DEV-{suf}',
        unidade='PC',
        ncm='84818200',
    )


class NFeEntradaFromSaidaDevolucaoTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username='dev_ep', password='x')
        self.empresa = _empresa()
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Devolucao',
            cnpj='98765432000188',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua C',
            numero='3',
            bairro='Centro',
            cep='01001000',
        )
        self.prod = _produto()
        self.chave = '35260112345678000199550010000000011123456789'
        self.nf = NFeSaida.objects.create(
            numero='NF-DEV-1',
            cliente=self.cliente,
            empresa_emitente=self.empresa,
            data=date.today(),
            valor_total=Decimal('100'),
            status='AUTORIZADA_PRODUCAO',
            status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
            ambiente_emissao=NFeSaida.AmbienteEmissao.PRODUCAO,
            chave_acesso=self.chave,
            serie_nfe='1',
            numero_nfe='000000001',
            protocolo_autorizacao='135260000000001',
        )
        ItemNFeSaida.objects.create(
            nf=self.nf,
            produto=self.prod,
            quantidade=Decimal('2'),
            valor=Decimal('50'),
            snapshot_produto={'descricao': 'Prod', 'unidade': 'PC', 'ncm': '84818200'},
            snapshot_fiscal={
                'cfop': '5102',
                'ncm': '84818200',
                'cst_icms': '00',
                'orig': '0',
                'base_icms': '100',
                'aliquota_icms': '18',
                'valor_icms': '18',
                'cst_pis': '01',
                'base_pis': '100',
                'aliquota_pis': '1.65',
                'valor_pis': '1.65',
                'cst_cofins': '01',
                'base_cofins': '100',
                'aliquota_cofins': '7.6',
                'valor_cofins': '7.6',
            },
        )
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_cfop_mapeamento(self) -> None:
        self.assertEqual(cfop_entrada_devolucao_from_saida('5102'), '1202')
        self.assertEqual(cfop_entrada_devolucao_from_saida('6102'), '2202')

    def test_gerar_rascunho_entrada(self) -> None:
        res = gerar_entrada_devolucao_from_nfe_saida(self.nf, usuario=self.user)
        self.assertTrue(res['ok'])
        self.assertFalse(res['ja_existia'])
        entrada = NFeEntrada.objects.get(pk=res['nf_entrada_id'])
        self.assertEqual(entrada.tipo_origem, NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA)
        self.assertEqual(entrada.fin_nfe, '4')
        self.assertEqual(entrada.chave_nfe_referenciada, self.chave)
        self.assertEqual(entrada.nfe_saida_origem_id, self.nf.pk)
        self.assertEqual(entrada.cliente_destinatario_id, self.cliente.pk)
        self.assertEqual(entrada.empresa_emitente_id, self.empresa.pk)
        item = ItemNFeEntrada.objects.get(nf=entrada)
        self.assertEqual(item.cfop, '1202')
        self.assertEqual(item.ncm, '84818200')
        self.assertEqual(item.quantidade, Decimal('2'))
        self.assertEqual(item.impostos_json['icms']['cst'], '00')

    def test_idempotente(self) -> None:
        r1 = gerar_entrada_devolucao_from_nfe_saida(self.nf, usuario=self.user)
        r2 = gerar_entrada_devolucao_from_nfe_saida(self.nf, usuario=self.user)
        self.assertFalse(r1['ja_existia'])
        self.assertTrue(r2['ja_existia'])
        self.assertEqual(r1['nf_entrada_id'], r2['nf_entrada_id'])
        self.assertEqual(NFeEntrada.objects.filter(nfe_saida_origem=self.nf).count(), 1)

    def test_api_gerar_entrada_devolucao(self) -> None:
        res = self.client_api.post(f'/api/nf-saidas/{self.nf.pk}/gerar-entrada-devolucao/', {}, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['nfe_entrada']['fin_nfe'], '4')

    def test_bloqueia_nao_autorizada(self) -> None:
        self.nf.status_emissao_sefaz = NFeSaida.StatusEmissaoSefaz.XML_ASSINADO
        self.nf.status = 'RASCUNHO'
        self.nf.save(update_fields=['status_emissao_sefaz', 'status'])
        res = self.client_api.post(f'/api/nf-saidas/{self.nf.pk}/gerar-entrada-devolucao/', {}, format='json')
        self.assertEqual(res.status_code, 400)
