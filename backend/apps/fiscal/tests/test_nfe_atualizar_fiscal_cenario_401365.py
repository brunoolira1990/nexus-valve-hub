"""ERP 4.0.13.6.5 — Atualizar fiscal usa cenário padrão de saída (não só legado)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe, preparar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.test_nfe_saida_faturamento import _cnpj, _faturamento_pronto, _produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida
from apps.regras_fiscais.saida_fiscal import buscar_regra_fiscal_nfe_saida_rascunho


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
            'ativo': True,
        },
    )
    return regra


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
            'ativo': True,
        },
    )
    return regra


def _nf_pa(*, ncm: str = '73079100') -> tuple[NFeSaida, ItemNFeSaida]:
    emp = Empresa.objects.create(razao_social='Emit SP', cnpj=_cnpj(), uf='SP')
    cli = Cliente.objects.create(
        razao_social='Cli PA',
        cnpj=_cnpj(),
        uf='PA',
        cidade='BELEM',
        cep='66630-505',
        logradouro='AV SALGADO FILHO',
        numero='S/N',
        bairro='VAL-DE-CAES',
    )
    pedido = PedidoVenda.objects.create(
        numero='PV-401365',
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


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=False)
class NFeAtualizarFiscalCenario401365Tests(TestCase):
    """Com flag global desligada, NF-e ainda deve achar regra no cenário padrão."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('nfe365', 'nfe365@test.com', 'x')
        _regra_sp_sp()
        _regra_sp_pa()

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_busca_servico_encontra_sp_pa_sem_flag_global(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': 'AV SALGADO FILHO',
            'bairro': 'VAL-DE-CAES',
            'complemento': '',
        }
        busca, regra, filtros = buscar_regra_fiscal_nfe_saida_rascunho(
            ncm='73079100',
            uf_origem='SP',
            uf_destino='PA',
        )
        self.assertIsNotNone(regra)
        self.assertEqual(busca['origem'], 'CENARIO_SAIDA')
        self.assertEqual(busca['cfop'], '6102')
        self.assertEqual(filtros['fonte_consultada'], 'CENARIO_SAIDA_PADRAO')

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_nao_aplica_sp_sp_quando_destino_pa(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': '',
            'bairro': '',
            'complemento': '',
        }
        busca, regra, _ = buscar_regra_fiscal_nfe_saida_rascunho(
            ncm='73079100',
            uf_origem='SP',
            uf_destino='PA',
        )
        self.assertIsNotNone(regra)
        self.assertEqual(busca['cfop'], '6102')
        self.assertNotEqual(busca['cfop'], '5102')

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_atualizar_fiscal_preview_encontra_regra_com_flag_global_off(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': 'AV SALGADO FILHO',
            'bairro': 'VAL-DE-CAES',
            'complemento': '',
        }
        nf, _ = _nf_pa()
        prev = preparar_atualizacao_impostos_nfe(nf)
        self.assertTrue(prev['pode_aplicar'], prev.get('alertas'))
        self.assertEqual(prev['resumo']['itens_com_regra'], 1)
        self.assertEqual(prev['resumo']['itens_sem_regra'], 0)
        self.assertEqual(prev['contexto_fiscal']['fonte_consultada'], 'CENARIO_SAIDA_PADRAO')
        self.assertIn('6102', str(prev['diagnosticos']))

    @patch('apps.cadastros.endereco_fiscal.consultar_cep_viacep')
    def test_atualizar_fiscal_aplica_cfop_6102(self, mock_cep):
        mock_cep.return_value = {
            'cidade': 'BELEM',
            'uf': 'PA',
            'cep': '66630-505',
            'logradouro': 'AV SALGADO FILHO',
            'bairro': 'VAL-DE-CAES',
            'complemento': '',
        }
        nf, nf_item = _nf_pa()
        qtd = nf_item.quantidade
        valor = nf_item.valor
        prod_id = nf_item.produto_id
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user)
        nf_item.refresh_from_db()
        snap = nf_item.snapshot_fiscal or {}
        self.assertEqual(snap.get('cfop') or snap.get('cfop_venda'), '6102')
        self.assertEqual(snap.get('ncm'), '73079100')
        self.assertEqual(nf_item.quantidade, qtd)
        self.assertEqual(nf_item.valor, valor)
        self.assertEqual(nf_item.produto_id, prod_id)
