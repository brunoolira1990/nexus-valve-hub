"""Gera rascunho de entrada própria a partir de NF-e Saída autorizada / importada XML."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.fiscal.models import (
    ItemNFeEntrada,
    ItemNFeSaida,
    ItemNFeSaidaHistoricaImportada,
    NFeEntrada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from apps.fiscal.nfe_entrada_from_saida_devolucao import (
    cfop_entrada_devolucao_from_saida,
    gerar_entrada_devolucao_from_nfe_saida,
    gerar_entrada_devolucao_from_nfe_saida_historica,
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
        self.assertEqual(cfop_entrada_devolucao_from_saida('5101'), '1201')
        self.assertEqual(cfop_entrada_devolucao_from_saida('5102'), '1202')
        self.assertEqual(cfop_entrada_devolucao_from_saida('6101'), '2201')
        self.assertEqual(cfop_entrada_devolucao_from_saida('6102'), '2202')
        self.assertEqual(cfop_entrada_devolucao_from_saida('5102', mesma_uf=False), '2202')
        self.assertEqual(cfop_entrada_devolucao_from_saida('6101', mesma_uf=True), '1201')

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
        # Lucro Presumido: PIS/COFINS CST 98 espelhando alíquotas da saída
        self.assertEqual(item.impostos_json['pis']['cst'], '98')
        self.assertEqual(item.impostos_json['cofins']['cst'], '98')
        self.assertEqual(str(item.impostos_json['pis']['aliquota']), '1.65')
        self.assertEqual(str(item.impostos_json['cofins']['aliquota']), '7.6')
        self.assertEqual(item.impostos_json['_meta']['perfil_devolucao'], 'lucro_presumido_2026')

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

    def test_aplica_regra_devolucao_venda(self) -> None:
        from apps.regras_fiscais.models import RegraFiscalEntrada

        RegraFiscalEntrada.objects.create(
            nome='Dev venda 5102',
            ativo=True,
            prioridade=10,
            tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.DEVOLUCAO_VENDA,
            cfop_origem='5102',
            cfop_entrada='1202',
            ncm='84818200',
            cst_icms_esperado='41',
            cst_pis_esperado='98',
            cst_cofins_esperado='98',
        )
        res = gerar_entrada_devolucao_from_nfe_saida(self.nf, usuario=self.user)
        self.assertTrue(res['ok'])
        item = ItemNFeEntrada.objects.get(nf_id=res['nf_entrada_id'])
        self.assertEqual(item.cfop, '1202')
        self.assertEqual(item.impostos_json['icms']['cst'], '41')
        self.assertEqual(item.impostos_json['pis']['cst'], '98')
        self.assertEqual(item.impostos_json['_meta']['regra_nome'], 'Dev venda 5102')
        self.assertEqual(item.impostos_json['_meta']['cfop_saida'], '5102')

        # Reaplicar via API
        api = self.client_api.post(
            f'/api/nf-entradas/{res["nf_entrada_id"]}/aplicar-regras-devolucao/',
            {},
            format='json',
        )
        self.assertEqual(api.status_code, 200, api.content)
        body = api.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['itens_com_regra'], 1)


class NFeEntradaFromSaidaHistoricaDevolucaoTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username='dev_ep_xml', password='x')
        self.empresa = _empresa()
        self.cliente = Cliente.objects.create(
            razao_social='Cliente Devolucao XML',
            cnpj='98765432000188',
            uf='SP',
            cidade='São Paulo',
            logradouro='Rua C',
            numero='3',
            bairro='Centro',
            cep='01001000',
        )
        self.prod = _produto()
        self.chave = '35260112345678000199550010000000021123456789'
        self.nf = NFeSaidaHistoricaImportada.objects.create(
            chave_acesso=self.chave,
            numero='000000002',
            serie='1',
            dh_emissao=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            tp_amb='1',
            nat_op='Venda',
            cstat='100',
            protocolo='135260000000002',
            valor_produtos=Decimal('100'),
            valor_total_nf=Decimal('100'),
            empresa_emitente=self.empresa,
            cliente=self.cliente,
            status_documento='autorizada',
            cancelada=False,
        )
        ItemNFeSaidaHistoricaImportada.objects.create(
            nf=self.nf,
            n_item=1,
            prod_json={
                'cProd': self.prod.codigo_completo,
                'xProd': 'Prod Devolucao',
                'NCM': '84818200',
                'CFOP': '5102',
                'uCom': 'PC',
                'qCom': '2',
                'vUnCom': '50.00',
                'vProd': '100.00',
            },
            imposto_json={
                'ICMS': {
                    'ICMS00': {
                        'orig': '0',
                        'CST': '00',
                        'vBC': '100.00',
                        'pICMS': '18.00',
                        'vICMS': '18.00',
                    }
                },
                'PIS': {'PISAliq': {'CST': '01', 'vBC': '100.00', 'pPIS': '1.65', 'vPIS': '1.65'}},
                'COFINS': {
                    'COFINSAliq': {'CST': '01', 'vBC': '100.00', 'pCOFINS': '7.60', 'vCOFINS': '7.60'}
                },
            },
        )
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_gerar_rascunho_entrada_historica(self) -> None:
        res = gerar_entrada_devolucao_from_nfe_saida_historica(self.nf, usuario=self.user)
        self.assertTrue(res['ok'])
        self.assertFalse(res['ja_existia'])
        entrada = NFeEntrada.objects.get(pk=res['nf_entrada_id'])
        self.assertEqual(entrada.tipo_origem, NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA)
        self.assertEqual(entrada.fin_nfe, '4')
        self.assertEqual(entrada.chave_nfe_referenciada, self.chave)
        self.assertEqual(entrada.nfe_saida_historica_origem_id, self.nf.pk)
        self.assertIsNone(entrada.nfe_saida_origem_id)
        self.assertEqual(entrada.cliente_destinatario_id, self.cliente.pk)
        item = ItemNFeEntrada.objects.get(nf=entrada)
        self.assertEqual(item.produto_id, self.prod.pk)
        self.assertEqual(item.cfop, '1202')
        self.assertEqual(item.quantidade, Decimal('2'))
        self.assertEqual(item.impostos_json['icms']['cst'], '00')
        self.assertEqual(item.impostos_json['pis']['cst'], '98')
        self.assertEqual(item.impostos_json['cofins']['cst'], '98')

    def test_idempotente_historica(self) -> None:
        r1 = gerar_entrada_devolucao_from_nfe_saida_historica(self.nf, usuario=self.user)
        r2 = gerar_entrada_devolucao_from_nfe_saida_historica(self.nf, usuario=self.user)
        self.assertFalse(r1['ja_existia'])
        self.assertTrue(r2['ja_existia'])
        self.assertEqual(r1['nf_entrada_id'], r2['nf_entrada_id'])
        self.assertEqual(NFeEntrada.objects.filter(nfe_saida_historica_origem=self.nf).count(), 1)

    def test_api_gerar_entrada_devolucao_historica(self) -> None:
        res = self.client_api.post(
            f'/api/nf-saidas-historicas-importadas/{self.nf.pk}/gerar-entrada-devolucao/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['nfe_entrada']['fin_nfe'], '4')

    def test_bloqueia_cancelada(self) -> None:
        self.nf.cancelada = True
        self.nf.status_documento = 'cancelada'
        self.nf.save(update_fields=['cancelada', 'status_documento'])
        res = self.client_api.post(
            f'/api/nf-saidas-historicas-importadas/{self.nf.pk}/gerar-entrada-devolucao/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_bloqueia_sem_produto_cadastro(self) -> None:
        ItemNFeSaidaHistoricaImportada.objects.filter(nf=self.nf).update(
            prod_json={
                'cProd': 'CODIGO-INEXISTENTE-XYZ',
                'xProd': 'Sem match',
                'NCM': '99999999',
                'CFOP': '5102',
                'uCom': 'PC',
                'qCom': '1',
                'vUnCom': '10.00',
                'vProd': '10.00',
            }
        )
        res = self.client_api.post(
            f'/api/nf-saidas-historicas-importadas/{self.nf.pk}/gerar-entrada-devolucao/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('produto', (res.json().get('mensagem') or '').lower())
