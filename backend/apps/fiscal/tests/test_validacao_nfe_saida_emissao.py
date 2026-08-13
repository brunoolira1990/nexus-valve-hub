"""NF-e Saída 2 — validação pré-emissão."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.faturamento_pedido_venda import confirmar_faturamento_pedido, criar_faturamento_pedido
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import AtendimentoEstoque, ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO, gerar_nfe_saida_from_faturamento
from apps.fiscal.validacao_nfe_saida import (
    STATUS_BLOQUEADA,
    STATUS_COM_PENDENCIAS,
    STATUS_PRONTA,
    TIPO_ALERTA,
    TIPO_PENDENCIA,
    validar_nfe_saida_para_emissao,
)
from apps.produtos.models import FamiliaProduto, Produto
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscalSaida


def _regra_vigente_84818200():
    """Cria regra vigente do cenário (NCM 84818200, SP->RJ) para os testes de validação."""
    cenario = garantir_cenario_saida_padrao()
    escopo, _ = CenarioFiscalSaidaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
        ncm='84818200',
    )
    regra, _ = RegraFiscalSaida.objects.update_or_create(
        escopo=escopo,
        cenario=cenario,
        uf_origem='SP',
        uf_destino='RJ',
        destinatario_contribuinte=RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
        defaults={
            'nome': 'Venda SP-RJ NCM 84818200',
            'cfop_venda': '5102',
            'cst_icms': '00',
            'aliquota_icms': Decimal('18'),
            'cst_pis': '01',
            'aliquota_pis': Decimal('1.65'),
            'cst_cofins': '01',
            'aliquota_cofins': Decimal('7.6'),
        },
    )
    return regra


def _cnpj() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _cliente_completo() -> Cliente:
    return Cliente.objects.create(
        razao_social='Cliente Validação',
        cnpj=_cnpj(),
        ie='123456789',
        logradouro='Rua A',
        cidade='Rio',
        uf='RJ',
        ativo=True,
    )


def _empresa_completa() -> Empresa:
    return Empresa.objects.create(
        razao_social='Emit Validação',
        cnpj=_cnpj(),
        uf='SP',
        regime_tributario='Lucro Presumido',
    )


def _produto() -> Produto:
    suf = uuid.uuid4().hex[:6].upper()
    fam = FamiliaProduto.objects.create(
        codigo_figura=f'V{suf}',
        descricao_base='Fam',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
        categoria_produto=FamiliaProduto.CategoriaProduto.PRODUTO_TECNICO,
    )
    return Produto.objects.create(
        familia=fam,
        descricao='Prod Val',
        modo_codigo=Produto.ModoCodigo.MANUAL,
        codigo_completo=f'PV-{suf}',
        unidade='PC',
        ncm='84818200',
    )


def _pedido_item(*, qtd=Decimal('2'), preco=Decimal('50'), cenario_vigente=True) -> tuple[PedidoVenda, ItemPedidoVenda]:
    if cenario_vigente:
        _regra_vigente_84818200()
    emp = _empresa_completa()
    cli = _cliente_completo()
    pedido = PedidoVenda.objects.create(
        numero=f'PV-{uuid.uuid4().hex[:6]}',
        empresa_emitente=emp,
        cliente=cli,
        data=date.today(),
        status='ABERTO',
        valor_total=Decimal('100'),
    )
    prod = _produto()
    item = ItemPedidoVenda.objects.create(
        pedido=pedido,
        produto=prod,
        quantidade=qtd,
        quantidade_negociada=qtd,
        valor_unitario=preco,
        preco_por_unidade_negociada=preco,
        snapshot_fiscal={
            'origem_regra_fiscal_saida': 'LEGADO',
            'ncm': '84818200',
            'cfop': '5102',
            'cst_icms': '00',
            'icms_saida_percentual': '18',
        },
    )
    return pedido, item


def _nf_faturamento() -> NFeSaida:
    pedido, item = _pedido_item()
    criado = criar_faturamento_pedido(pedido, {'itens': [{'item_pedido_id': item.pk, 'quantidade': '2'}]})
    confirmar_faturamento_pedido(pedido, criado['faturamento_id'])
    fat = FaturamentoPedidoVenda.objects.get(pk=criado['faturamento_id'])
    r = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
    nf_criada = NFeSaida.objects.prefetch_related('itens__produto').select_related(
        'cliente', 'pedido_venda__empresa_emitente', 'faturamento_pedido_venda'
    ).get(pk=r['nfe_saida_id'])
    nf_criada.indicadores_fiscais_confirmados = True
    nf_criada.save(update_fields=['indicadores_fiscais_confirmados'])
    return nf_criada


class ValidacaoNFeSaidaEmissaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('val_nfe', 'val@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _get_validacao(self, nf_id: int):
        return self.client.get(f'/api/nf-saidas/{nf_id}/validar-emissao/')

    def test_rascunho_faturamento_pronta_ou_alertas_sem_pendencias(self):
        nf = _nf_faturamento()
        data = validar_nfe_saida_para_emissao(nf)
        self.assertNotEqual(data['status_prontidao'], STATUS_COM_PENDENCIAS)
        self.assertEqual(data['total_pendencias'], 0)
        self.assertIn(data['status_prontidao'], (STATUS_PRONTA, 'COM_ALERTAS'))

    def test_sem_cliente_pendencia(self):
        nf = _nf_faturamento()
        nf.cliente_id = None
        data = validar_nfe_saida_para_emissao(nf)
        self.assertEqual(data['status_prontidao'], STATUS_COM_PENDENCIAS)
        codigos = [x['codigo'] for x in data['grupos']['cliente']]
        self.assertIn('CLIENTE_NAO_INFORMADO', codigos)

    def test_sem_itens_pendencia(self):
        nf = _nf_faturamento()
        nf.itens.all().delete()
        data = validar_nfe_saida_para_emissao(nf)
        self.assertGreater(data['total_pendencias'], 0)
        self.assertTrue(any(x['codigo'] == 'NFE_SEM_ITENS' for x in data['grupos']['itens']))

    def test_item_qtd_zero_pendencia(self):
        nf = _nf_faturamento()
        ItemNFeSaida.objects.filter(nf=nf).update(quantidade=0)
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(any(x['codigo'] == 'ITEM_QTD_ZERO' for x in data['grupos']['itens']))

    def test_item_sem_ncm_pendencia(self):
        nf = _nf_faturamento()
        item = nf.itens.get()
        item.snapshot_fiscal = {'cfop': '5102'}
        item.snapshot_produto = {}
        item.produto.ncm = ''
        item.produto.save(update_fields=['ncm'])
        item.save(update_fields=['snapshot_fiscal', 'snapshot_produto'])
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(any(x['codigo'] == 'ITEM_SEM_NCM' for x in data['grupos']['fiscal']))

    def test_item_sem_cfop_pendencia(self):
        nf = _nf_faturamento()
        item = nf.itens.get()
        item.snapshot_fiscal = {'ncm': '84818200'}
        item.save(update_fields=['snapshot_fiscal'])
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(any(x['codigo'] == 'ITEM_SEM_CFOP' for x in data['grupos']['fiscal']))

    def test_item_sem_snapshot_faturamento_pendencia(self):
        nf = _nf_faturamento()
        item = nf.itens.get()
        item.snapshot_fiscal = None
        item.save(update_fields=['snapshot_fiscal'])
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(
            any(
                x['codigo'] == 'ITEM_SEM_SNAPSHOT_FISCAL' and x['tipo'] == TIPO_PENDENCIA
                for x in data['grupos']['fiscal']
            ),
        )

    def test_total_divergente_pendencia(self):
        nf = _nf_faturamento()
        nf.valor_total = Decimal('9999')
        nf.save(update_fields=['valor_total'])
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(any(x['codigo'] == 'NFE_TOTAL_DIVERGENTE_ITENS' for x in data['grupos']['valores']))

    def test_faturamento_vinculo(self):
        nf = _nf_faturamento()
        data = validar_nfe_saida_para_emissao(nf)
        self.assertFalse(any(x['codigo'] == 'FATURAMENTO_STATUS_INVALIDO' for x in data['grupos']['origem']))
        self.assertFalse(any(x['codigo'] == 'PEDIDO_NAO_VINCULADO' for x in data['grupos']['origem']))

    def test_manual_alerta_origem(self):
        pedido, item = _pedido_item()
        cli = pedido.cliente
        nf = NFeSaida.objects.create(
            numero='RASCUNHO-MANUAL-VAL',
            cliente=cli,
            data=date.today(),
            status=STATUS_NFE_RASCUNHO,
            valor_total=Decimal('10'),
            pedido_venda=pedido,
        )
        ItemNFeSaida.objects.create(
            nf=nf,
            produto=item.produto,
            quantidade=Decimal('1'),
            valor=Decimal('10'),
            snapshot_fiscal={'ncm': '84818200', 'cfop': '5102', 'cst_icms': '00'},
            snapshot_produto={'descricao_produto_snapshot': 'X', 'unidade_snapshot': 'PC'},
        )
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['indicadores_fiscais_confirmados'])
        nf = NFeSaida.objects.select_related('cliente', 'pedido_venda__empresa_emitente').get(pk=nf.pk)
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(
            any(x['codigo'] == 'NFE_ORIGEM_MANUAL' and x['tipo'] == TIPO_ALERTA for x in data['grupos']['origem']),
        )
        self.assertTrue(
            any(
                x['codigo'] == 'ITEM_SEM_SNAPSHOT_FISCAL' and x['tipo'] == TIPO_ALERTA
                for x in data['grupos']['fiscal']
            )
            or data['total_pendencias'] == 0,
        )

    def test_nao_movimenta_estoque_nem_financeiro(self):
        nf = _nf_faturamento()
        atend_antes = AtendimentoEstoque.objects.count()
        titulos_antes = list(nf.titulos_receber or [])
        validar_nfe_saida_para_emissao(nf)
        self.assertEqual(AtendimentoEstoque.objects.count(), atend_antes)
        nf.refresh_from_db()
        self.assertEqual(nf.titulos_receber, titulos_antes)

    def test_emitida_bloqueada(self):
        nf = _nf_faturamento()
        nf.status = 'Emitida'
        nf.save(update_fields=['status'])
        data = validar_nfe_saida_para_emissao(nf)
        self.assertEqual(data['status_prontidao'], STATUS_BLOQUEADA)
        self.assertFalse(data['pode_emitir'])

    def test_api_validar_emissao(self):
        nf = _nf_faturamento()
        r = self._get_validacao(nf.pk)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['nfe_saida_id'], nf.pk)
        self.assertIn('grupos', r.json())

    def test_cliente_sem_cnpj_pendencia(self):
        nf = _nf_faturamento()
        cli = nf.cliente
        cli.cnpj = ''
        cli.save(update_fields=['cnpj'])
        data = validar_nfe_saida_para_emissao(nf)
        self.assertTrue(any(x['codigo'] == 'CLIENTE_SEM_DOCUMENTO' for x in data['grupos']['cliente']))
