"""ERP 4.0.13.6.4 — consistência fiscal de endereço do cliente."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.endereco_fiscal import validar_endereco_fiscal
from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe, preparar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.test_nfe_saida_faturamento import _cnpj, _faturamento_pronto, _pedido_item, _produto
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _cep_belem_pa() -> dict[str, str]:
    return {
        'logradouro': 'AV SALGADO FILHO',
        'complemento': '',
        'bairro': 'VAL-DE-CAES',
        'cidade': 'BELEM',
        'uf': 'PA',
        'cep': '66630-505',
    }


def _regra_sp_sp(ncm: str = '73079100') -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='SP',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'SP interno',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('0.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('3'),
        },
    )
    return regra


def _regra_sp_pa(ncm: str = '73079100') -> RegraFiscalSaida:
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm=ncm,
        defaults={},
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='PA',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'SP para PA',
            'cfop_venda': '6102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('12'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('0.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('3'),
        },
    )
    return regra


def _nf_com_cliente_inconsistente(*, ncm: str = '73079100') -> tuple[NFeSaida, ItemNFeSaida]:
    emp = Empresa.objects.create(razao_social='Emit SP', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(
        razao_social='PETROBRAS TRANSPORTE S.A - TRANSPETRO',
        cnpj=_cnpj(),
        ie='15-220462-8',
        cep='66630-505',
        logradouro='AV SALGADO FILHO',
        numero='S/N',
        bairro='VAL-DE-CAES',
        cidade='BELEM',
        uf='SP',
    )
    pedido = PedidoVenda.objects.create(
        numero='PV-401361',
        empresa_emitente=emp,
        cliente=cli,
        data='2026-05-27',
        status='ABERTO',
        valor_total=Decimal('500'),
    )
    prod = _produto()
    prod.ncm = ncm
    prod.save(update_fields=['ncm'])
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=Decimal('2'),
        quantidade_negociada=Decimal('2'),
        valor_unitario=Decimal('250'),
        preco_por_unidade_negociada=Decimal('250'),
        snapshot_fiscal={'ncm': ncm},
    )
    fat = _faturamento_pronto(pedido, item, qtd='2')
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    nf = NFeSaida.objects.prefetch_related('itens__produto').get(pk=r['nfe_saida_id'])
    nf_item = nf.itens.first()
    assert nf_item is not None
    nf_item.snapshot_fiscal = {}
    nf_item.save(update_fields=['snapshot_fiscal'])
    return nf, nf_item


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class EnderecoFiscalClienteTests(TestCase):
    def test_cliente_endereco_coerente_passa_validacao(self):
        cli = Cliente.objects.create(
            razao_social='Cliente SP',
            cnpj=_cnpj(),
            cep='01310-100',
            logradouro='Av Paulista',
            numero='1000',
            bairro='Bela Vista',
            cidade='SAO PAULO',
            uf='SP',
        )
        with patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value={
            'cidade': 'SAO PAULO',
            'uf': 'SP',
            'cep': '01310-100',
            'logradouro': 'Av Paulista',
            'bairro': 'Bela Vista',
            'complemento': '',
        }):
            result = validar_endereco_fiscal(cli, consultar_cep=True)
        self.assertTrue(result.consistente)
        self.assertFalse(result.bloqueio_fiscal)
        self.assertEqual(result.uf_destino, 'SP')

    def test_cliente_belem_cep_sp_gera_inconsistencia(self):
        cli = Cliente.objects.create(
            razao_social='PETROBRAS TRANSPORTE S.A - TRANSPETRO',
            cnpj=_cnpj(),
            cep='66630-505',
            logradouro='AV SALGADO FILHO',
            numero='S/N',
            bairro='VAL-DE-CAES',
            cidade='BELEM',
            uf='SP',
        )
        with patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=_cep_belem_pa()):
            result = validar_endereco_fiscal(cli, consultar_cep=True)
        self.assertFalse(result.consistente)
        self.assertTrue(result.bloqueio_fiscal)
        self.assertIn('66630-505', result.alertas[0])
        self.assertIn('PA', result.alertas[0])

    def test_cliente_serializer_expoe_endereco_fiscal(self):
        cli = Cliente.objects.create(razao_social='Cli', cnpj=_cnpj(), cidade='BELEM', uf='SP', cep='66630-505')
        user = get_user_model().objects.create_user('cad401', 'cad401@test.com', 'x')
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/clientes/{cli.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('endereco_fiscal', resp.data)


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class NFeEnderecoFiscalDiagnosticoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe401', 'nfe401@test.com', 'x')
        _regra_sp_sp()

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=_cep_belem_pa())
    def test_nfe_nao_aplica_regra_sp_sp_com_endereco_inconsistente(self, _mock_cep):
        nf, _ = _nf_com_cliente_inconsistente()
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertFalse(prev['pode_aplicar'])
        self.assertEqual(prev['resumo']['itens_sem_regra'], 1)
        self.assertIn('66630-505', prev['alertas'][0])
        diag = prev['diagnosticos'][0]
        self.assertEqual(diag['tipo'], 'ENDERECO_INCONSISTENTE')

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=_cep_belem_pa())
    def test_nfe_validacao_informa_endereco_inconsistente(self, _mock_cep):
        nf, _ = _nf_com_cliente_inconsistente()
        val = validar_nfe_saida_para_emissao(nf)
        codigos = [
            item['codigo']
            for lista in val['grupos'].values()
            for item in lista
        ]
        self.assertIn('CLIENTE_ENDERECO_FISCAL_INCONSISTENTE', codigos)
        msgs = ' '.join(item['mensagem'] for lista in val['grupos'].values() for item in lista)
        self.assertIn('66630-505', msgs)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=_cep_belem_pa())
    def test_nfe_informa_falta_regra_sp_pa_quando_destino_corrigido(self, _mock_cep):
        nf, nf_item = _nf_com_cliente_inconsistente()
        nf.cliente.uf = 'PA'
        nf.cliente.save(update_fields=['uf'])
        nf.refresh_from_db()
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertFalse(prev['pode_aplicar'])
        detalhe = prev['diagnosticos'][0]['detalhe']
        self.assertIn('73079100', detalhe)
        self.assertIn('SP', detalhe)
        self.assertIn('PA', detalhe)

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=_cep_belem_pa())
    def test_nfe_aplica_regra_sp_pa_quando_existe(self, _mock_cep):
        _regra_sp_pa()
        nf, nf_item = _nf_com_cliente_inconsistente()
        nf.cliente.uf = 'PA'
        nf.cliente.save(update_fields=['uf'])
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['pode_aplicar'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        snap = nf_item.snapshot_fiscal or {}
        self.assertEqual(snap.get('cfop') or snap.get('cfop_venda'), '6102')
        self.assertTrue(snap.get('cst_icms'))

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value={
        'cidade': 'SAO PAULO',
        'uf': 'SP',
        'cep': '01310-100',
        'logradouro': 'Av Paulista',
        'bairro': 'Centro',
        'complemento': '',
    })
    def test_nfe_aplica_regra_sp_sp_cliente_sp(self, _mock_cep):
        _regra_sp_sp('84818200')
        pedido, item = _pedido_item()
        item.snapshot_fiscal = {'ncm': '73079100'}
        item.save(update_fields=['snapshot_fiscal'])
        pedido.cliente.cep = '01310-100'
        pedido.cliente.cidade = 'SAO PAULO'
        pedido.cliente.uf = 'SP'
        pedido.cliente.logradouro = 'Av Paulista'
        pedido.cliente.numero = '100'
        pedido.cliente.bairro = 'Centro'
        pedido.cliente.save()
        fat = _faturamento_pronto(pedido, item)
        r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=r['nfe_saida_id'])
        nf_item = nf.itens.first()
        nf_item.snapshot_fiscal = {}
        nf_item.save(update_fields=['snapshot_fiscal'])
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['pode_aplicar'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        self.assertEqual((nf_item.snapshot_fiscal or {}).get('cfop'), '5102')

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep', return_value=_cep_belem_pa())
    def test_atualizar_fiscal_nao_altera_comercial(self, _mock_cep):
        _regra_sp_pa()
        nf, nf_item = _nf_com_cliente_inconsistente()
        nf.cliente.uf = 'PA'
        nf.cliente.save(update_fields=['uf'])
        qtd = nf_item.quantidade
        valor = nf_item.valor
        prod_id = nf_item.produto_id
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        self.assertEqual(nf_item.quantidade, qtd)
        self.assertEqual(nf_item.valor, valor)
        self.assertEqual(nf_item.produto_id, prod_id)
