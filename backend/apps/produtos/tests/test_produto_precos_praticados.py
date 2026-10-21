"""Últimos preços praticados no payload do produto: NF-e, conferência de NF-e e pedido de compra."""

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cadastros.models import Cliente, Fornecedor
from apps.comercial.models import ItemPedidoCompra, PedidoCompra
from apps.fiscal.models import (
    ItemNFeEntrada,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaida,
    NFeEntrada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
    NFeSaida,
)
from apps.produtos.models import Produto
from apps.produtos.painel_operacional import montar_painel_resumo_produto
from apps.produtos.precos_praticados import annotate_ultimos_precos
from apps.produtos.serializers import ProdutoSerializer

# NFeSaida exige exatamente um destinatário (cliente ou fornecedor), então cada venda cria um cliente.
_CONTADOR = [0]


def _produto(codigo: str, **campos) -> Produto:
    base = {
        'descricao': 'FLANGE CEGO ACO CARBONO ANSI 150# RF',
        'modo_codigo': Produto.ModoCodigo.MANUAL,
        'codigo_completo': codigo,
        'unidade': 'PC',
    }
    base.update(campos)
    return Produto.objects.create(**base)


def _entrada(produto: Produto, *, numero: str, data: date, status, valor: Decimal, quantidade: Decimal) -> None:
    nf = NFeEntrada.objects.create(
        numero=numero,
        data=data,
        tipo_origem=NFeEntrada.TipoOrigem.MANUAL,
        status_operacional=status,
    )
    ItemNFeEntrada.objects.create(
        nf=nf,
        produto=produto,
        quantidade=quantidade,
        valor=valor,
    )


def _saida(produto: Produto, *, numero: str, data: date, status: str, valor: Decimal, quantidade: Decimal) -> None:
    cliente = Cliente.objects.create(
        razao_social=f'Cliente {numero}',
        cnpj=f'98.765.432/0001-{_CONTADOR[0]:02d}',
    )
    _CONTADOR[0] += 1
    nf = NFeSaida.objects.create(numero=numero, data=data, status=status, cliente=cliente)
    ItemNFeSaida.objects.create(
        nf=nf,
        produto=produto,
        quantidade=quantidade,
        valor=valor,
    )


def _pedido_compra(
    produto: Produto,
    *,
    numero: str,
    data: date,
    status: str,
    valor_unitario: Decimal,
    quantidade: Decimal = Decimal('1.000'),
) -> PedidoCompra:
    _CONTADOR[0] += 1
    fornecedor = Fornecedor.objects.create(
        razao_social=f'Fornecedor {numero}',
        cnpj=f'97.654.321/0001-{_CONTADOR[0]:02d}',
    )
    pedido = PedidoCompra.objects.create(numero=numero, fornecedor=fornecedor, data=data, status=status)
    ItemPedidoCompra.objects.create(
        pedido=pedido,
        produto=produto,
        quantidade=quantidade,
        valor_unitario=valor_unitario,
        valor_total_item=valor_unitario * quantidade,
    )
    return pedido


def _conferencia_entrada(
    produto: Produto,
    *,
    numero: str,
    dh_emissao: datetime,
    valor_unitario: Decimal,
    quantidade: Decimal = Decimal('2.000'),
    status: str = ItemNFeEntradaConferencia.Status.CONFERIDO,
) -> ItemNFeEntradaConferencia:
    """NF-e de entrada emitida fora do ERP: o preço chega pela conferência do XML importado."""
    _CONTADOR[0] += 1
    nf_hist = NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'{_CONTADOR[0]:044d}',
        numero=numero,
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(dh_emissao),
    )
    item_hist = ItemNFeEntradaHistoricaImportada.objects.create(nf=nf_hist, n_item=1)
    conferencia = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf_hist)
    return ItemNFeEntradaConferencia.objects.create(
        conferencia=conferencia,
        item_nfe_historico=item_hist,
        produto=produto,
        status=status,
        quantidade_nf=quantidade,
        valor_unitario_nf=valor_unitario,
        valor_total_nf=valor_unitario * quantidade,
    )


class ProdutoSerializerUltimosPrecosTests(TestCase):
    def test_ultimo_preco_compra_vem_da_nfe_entrada_autorizada_sem_dividir_pela_quantidade(self):
        produto = _produto('PRC-001')
        _entrada(
            produto,
            numero='EP-PRC-1',
            data=date(2026, 9, 10),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('900.00'),
            quantidade=Decimal('8.000'),
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['preco_custo'], 0.0)
        self.assertEqual(data['ultimo_preco_compra'], 900.0)

    def test_ultimo_preco_venda_vem_da_nfe_saida_autorizada(self):
        produto = _produto('PRC-002', preco_venda=Decimal('1000.00'))
        _saida(
            produto,
            numero='NF-PRC-2',
            data=date(2026, 9, 11),
            status='AUTORIZADA_PRODUCAO',
            valor=Decimal('1234.5678'),
            quantidade=Decimal('3.000'),
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['preco_venda'], 1000.0)
        self.assertAlmostEqual(data['ultimo_preco_venda'], 1234.5678, places=4)

    def test_documento_nao_realizado_nao_conta_como_preco_praticado(self):
        produto = _produto('PRC-003')
        _entrada(
            produto,
            numero='EP-PRC-OK',
            data=date(2026, 9, 1),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('500.00'),
            quantidade=Decimal('2.000'),
        )
        _entrada(
            produto,
            numero='EP-PRC-CANCELADA',
            data=date(2026, 10, 5),
            status=NFeEntrada.StatusOperacional.CANCELADA_PRODUCAO,
            valor=Decimal('610.00'),
            quantidade=Decimal('2.000'),
        )
        _saida(
            produto,
            numero='NF-PRC-CANCELADA',
            data=date(2026, 10, 6),
            status='CANCELADA_PRODUCAO',
            valor=Decimal('777.00'),
            quantidade=Decimal('1.000'),
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['ultimo_preco_compra'], 500.0)
        self.assertIsNone(data['ultimo_preco_venda'])

    def test_venda_autorizada_no_ciclo_interno_tambem_conta(self):
        produto = _produto('PRC-004')
        _saida(
            produto,
            numero='NF-PRC-INT',
            data=date(2026, 8, 20),
            status='AUTORIZADA_INTERNA',
            valor=Decimal('250.00'),
            quantidade=Decimal('5.000'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_venda'], 250.0)

    def test_produto_sem_nfe_devolve_nulo_para_os_dois_precos(self):
        data = ProdutoSerializer(_produto('PRC-005')).data
        self.assertIsNone(data['ultimo_preco_compra'])
        self.assertIsNone(data['ultimo_preco_venda'])

    def test_considera_a_linha_mais_recente_por_data_da_nf(self):
        produto = _produto('PRC-006')
        _entrada(
            produto,
            numero='EP-PRC-ANTIGA',
            data=date(2026, 3, 1),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('120.00'),
            quantidade=Decimal('1.000'),
        )
        _entrada(
            produto,
            numero='EP-PRC-NOVA',
            data=date(2026, 7, 15),
            status=NFeEntrada.StatusOperacional.IMPORTADA_PENDENTE_CONFERENCIA,
            valor=Decimal('143.50'),
            quantidade=Decimal('4.000'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_compra'], 143.5)

    def test_queryset_anotado_devolve_o_mesmo_valor_da_consulta_por_instancia(self):
        produto = _produto('PRC-007')
        _saida(
            produto,
            numero='NF-PRC-7',
            data=date(2026, 6, 1),
            status='AUTORIZADA_PRODUCAO',
            valor=Decimal('310.00'),
            quantidade=Decimal('2.000'),
        )
        anotado = annotate_ultimos_precos(Produto.objects.filter(pk=produto.pk)).first()
        self.assertEqual(
            ProdutoSerializer(anotado).data['ultimo_preco_venda'],
            ProdutoSerializer(produto).data['ultimo_preco_venda'],
        )

    def test_sem_nfe_de_entrada_o_preco_vem_do_pedido_de_compra_mais_recente(self):
        produto = _produto('PRC-008')
        _pedido_compra(
            produto,
            numero='PC-PRC-ANTIGO',
            data=date(2026, 4, 1),
            status='Recebido',
            valor_unitario=Decimal('40.00'),
        )
        _pedido_compra(
            produto,
            numero='PC-PRC-NOVO',
            data=date(2026, 9, 30),
            status='PENDENTE',
            valor_unitario=Decimal('87.50'),
        )
        data = ProdutoSerializer(produto).data
        self.assertEqual(data['ultimo_preco_compra'], 87.5)
        self.assertIsNone(data['ultimo_preco_venda'])

    def test_nfe_valida_ganha_do_pedido_mesmo_pedido_sendo_mais_recente(self):
        produto = _produto('PRC-009')
        _entrada(
            produto,
            numero='EP-PRC-9',
            data=date(2026, 5, 1),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('500.00'),
            quantidade=Decimal('2.000'),
        )
        _pedido_compra(
            produto,
            numero='PC-PRC-9',
            data=date(2026, 10, 5),
            status='APROVADO',
            valor_unitario=Decimal('900.00'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_compra'], 500.0)

    def test_pedido_cancelado_nao_conta_como_preco_praticado(self):
        produto = _produto('PRC-010')
        _pedido_compra(
            produto,
            numero='PC-PRC-OK',
            data=date(2026, 3, 1),
            status='APROVADO',
            valor_unitario=Decimal('60.00'),
        )
        _pedido_compra(
            produto,
            numero='PC-PRC-CANCELADO',
            data=date(2026, 10, 1),
            status='CANCELADO',
            valor_unitario=Decimal('99.00'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_compra'], 60.0)

        produto_sem_pedido_valido = _produto('PRC-011')
        _pedido_compra(
            produto_sem_pedido_valido,
            numero='PC-PRC-SO-CANCELADO',
            data=date(2026, 10, 1),
            status='Cancelada',
            valor_unitario=Decimal('99.00'),
        )
        self.assertIsNone(ProdutoSerializer(produto_sem_pedido_valido).data['ultimo_preco_compra'])

    def test_anotacao_aplica_o_fallback_de_pedido_e_bate_com_a_consulta_por_instancia(self):
        produto = _produto('PRC-012')
        _pedido_compra(
            produto,
            numero='PC-PRC-12',
            data=date(2026, 8, 1),
            status='Parcialmente recebido',
            valor_unitario=Decimal('1234.56'),
        )
        anotado = annotate_ultimos_precos(Produto.objects.filter(pk=produto.pk)).first()
        self.assertEqual(anotado.ultimo_preco_compra, Decimal('1234.56'))
        self.assertEqual(
            ProdutoSerializer(anotado).data['ultimo_preco_compra'],
            ProdutoSerializer(produto).data['ultimo_preco_compra'],
        )


class ConferenciaNFeEntradaPrecoTests(TestCase):
    """Segundo degrau da hierarquia: NF-e importada conferida, sem entrada correspondente no ERP."""

    def test_sem_nfe_de_entrada_a_conferencia_importada_fornece_o_preco(self):
        produto = _produto('CNF-001')
        _conferencia_entrada(
            produto,
            numero='15395',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.06'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_compra'], 78.06)

    def test_nfe_entrada_autorizada_ganha_da_conferencia_mesmo_conferencia_sendo_mais_recente(self):
        produto = _produto('CNF-002')
        _entrada(
            produto,
            numero='EP-CNF-2',
            data=date(2026, 9, 23),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('145.58'),
            quantidade=Decimal('2.000'),
        )
        _conferencia_entrada(
            produto,
            numero='15395',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.06'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_compra'], 145.58)

    def test_conferencia_ganha_do_pedido_mesmo_pedido_sendo_mais_recente(self):
        produto = _produto('CNF-003')
        _conferencia_entrada(
            produto,
            numero='15396',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.06'),
        )
        _pedido_compra(
            produto,
            numero='PC-CNF-3',
            data=date(2026, 10, 10),
            status='APROVADO',
            valor_unitario=Decimal('900.00'),
        )
        self.assertEqual(ProdutoSerializer(produto).data['ultimo_preco_compra'], 78.06)

    def test_item_ignorado_da_conferencia_nao_conta_como_preco_praticado(self):
        produto = _produto('CNF-004')
        _conferencia_entrada(
            produto,
            numero='15397',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.06'),
            status=ItemNFeEntradaConferencia.Status.IGNORADO,
        )
        self.assertIsNone(ProdutoSerializer(produto).data['ultimo_preco_compra'])

    def test_anotacao_da_conferencia_bate_com_a_consulta_por_instancia(self):
        produto = _produto('CNF-005')
        _conferencia_entrada(
            produto,
            numero='15398',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.0613'),
        )
        anotado = annotate_ultimos_precos(Produto.objects.filter(pk=produto.pk)).first()
        self.assertEqual(anotado.ultimo_preco_compra, Decimal('78.0613'))
        self.assertEqual(
            ProdutoSerializer(anotado).data['ultimo_preco_compra'],
            ProdutoSerializer(produto).data['ultimo_preco_compra'],
        )


class PainelHierarquiaUltimaCompraTests(TestCase):
    """O card 'Última compra' decide pela hierarquia de fontes, nunca por recência entre fontes."""

    def _nf_e_pedido_mais_novo(self, produto: Produto) -> None:
        _entrada(
            produto,
            numero='EP-HIQ-1',
            data=date(2026, 5, 1),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('500.00'),
            quantidade=Decimal('2.000'),
        )
        _pedido_compra(
            produto,
            numero='PC-HIQ-MAIS-NOVO',
            data=date(2026, 10, 5),
            status='APROVADO',
            valor_unitario=Decimal('900.00'),
        )

    def test_painel_nao_troca_a_nfe_entrada_por_um_pedido_mais_recente(self):
        produto = _produto('HIQ-001')
        self._nf_e_pedido_mais_novo(produto)
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(painel['ultima_compra']['origem'], 'nfe_entrada')
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('500.00'))

    def test_painel_nao_troca_a_nfe_entrada_por_uma_conferencia_mais_recente(self):
        produto = _produto('HIQ-002')
        _entrada(
            produto,
            numero='EP-HIQ-2',
            data=date(2026, 9, 23),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('145.58'),
            quantidade=Decimal('2.000'),
        )
        _conferencia_entrada(
            produto,
            numero='15395',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.06'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(painel['ultima_compra']['origem'], 'nfe_entrada')
        self.assertEqual(
            Decimal(painel['ultima_compra']['valor_unitario']),
            Decimal(str(ProdutoSerializer(produto).data['ultimo_preco_compra'])),
        )

    def test_sem_nfe_de_entrada_o_painel_usa_a_conferencia_e_bate_com_a_aba_geral(self):
        produto = _produto('HIQ-003')
        _conferencia_entrada(
            produto,
            numero='15400',
            dh_emissao=datetime(2026, 9, 25, 8, 0),
            valor_unitario=Decimal('78.0613'),
        )
        _pedido_compra(
            produto,
            numero='PC-HIQ-MAIS-NOVO',
            data=date(2026, 10, 5),
            status='APROVADO',
            valor_unitario=Decimal('900.00'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(painel['ultima_compra']['origem'], 'nfe_entrada_conferencia')
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('78.0613'))
        self.assertEqual(
            Decimal(painel['ultima_compra']['valor_unitario']),
            Decimal(str(ProdutoSerializer(produto).data['ultimo_preco_compra'])),
        )

    def test_painel_descarta_pedido_cancelado_do_card_e_bate_com_a_aba_geral(self):
        produto = _produto('HIQ-005')
        _pedido_compra(
            produto,
            numero='PC-HIQ-OK',
            data=date(2026, 3, 1),
            status='APROVADO',
            valor_unitario=Decimal('60.00'),
        )
        _pedido_compra(
            produto,
            numero='PC-HIQ-CANCELADO',
            data=date(2026, 10, 1),
            status='CANCELADO',
            valor_unitario=Decimal('99.00'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(painel['ultima_compra']['pedido_compra_numero'], 'PC-HIQ-OK')
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('60.00'))
        self.assertEqual(
            Decimal(painel['ultima_compra']['valor_unitario']),
            Decimal(str(ProdutoSerializer(produto).data['ultimo_preco_compra'])),
        )
        # a lista de documentos continua mostrando o pedido cancelado
        self.assertIn(
            'PC-HIQ-CANCELADO',
            [linha['pedido_compra_numero'] for linha in painel['historico_compras']],
        )

    def test_pedido_cancelado_como_unica_fonte_deixa_card_e_aba_geral_sem_preco(self):
        produto = _produto('HIQ-006')
        _pedido_compra(
            produto,
            numero='PC-HIQ-SO-CANCELADO',
            data=date(2026, 10, 1),
            status='Cancelada',
            valor_unitario=Decimal('99.00'),
        )
        self.assertIsNone(montar_painel_resumo_produto(produto)['ultima_compra'])
        self.assertIsNone(ProdutoSerializer(produto).data['ultimo_preco_compra'])

    def test_painel_mantem_o_pedido_de_compra_como_ultima_fonte(self):
        produto = _produto('HIQ-004')
        _entrada(
            produto,
            numero='EP-HIQ-4-CANCELADA',
            data=date(2026, 10, 1),
            status=NFeEntrada.StatusOperacional.CANCELADA_PRODUCAO,
            valor=Decimal('500.00'),
            quantidade=Decimal('2.000'),
        )
        _pedido_compra(
            produto,
            numero='PC-HIQ-4',
            data=date(2026, 9, 5),
            status='APROVADO',
            valor_unitario=Decimal('900.00'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(painel['ultima_compra']['origem'], 'pedido_compra')
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('900.00'))


class PainelOperacionalPrecosTests(TestCase):
    """A aba Painel tem que mostrar o mesmo número que a aba Geral."""

    def test_painel_usa_o_valor_do_item_como_unitario_e_multiplica_para_o_total(self):
        produto = _produto('PNL-001')
        _entrada(
            produto,
            numero='EP-PNL-1',
            data=date(2026, 9, 10),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('900.00'),
            quantidade=Decimal('8.000'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('900.00'))
        self.assertEqual(Decimal(painel['ultima_nf_entrada']['valor_unitario']), Decimal('900.00'))
        linha = next(r for r in painel['historico_compras'] if r['origem'] == 'nfe_entrada')
        self.assertEqual(Decimal(linha['valor_unitario']), Decimal('900.00'))
        self.assertEqual(Decimal(linha['valor_total']), Decimal('7200.00'))
        fiscal = next(r for r in painel['fiscal']['nf_entrada'] if r['origem'] == 'nfe_entrada')
        self.assertEqual(Decimal(fiscal['valor_unitario']), Decimal('900.00'))
        self.assertEqual(Decimal(fiscal['valor_total']), Decimal('7200.00'))

    def test_painel_de_saida_tambem_trata_o_valor_do_item_como_unitario(self):
        produto = _produto('PNL-002')
        _saida(
            produto,
            numero='NF-PNL-2',
            data=date(2026, 9, 11),
            status='AUTORIZADA_PRODUCAO',
            valor=Decimal('100.00'),
            quantidade=Decimal('3.500'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(Decimal(painel['ultima_nf_saida']['valor_unitario']), Decimal('100.00'))
        linha = next(r for r in painel['historico_vendas'] if r['origem'] == 'nfe_saida')
        self.assertEqual(Decimal(linha['valor_unitario']), Decimal('100.00'))
        self.assertEqual(Decimal(linha['valor_total']), Decimal('350.00'))
        fiscal = painel['fiscal']['nf_saida'][0]
        self.assertEqual(Decimal(fiscal['valor_unitario']), Decimal('100.00'))
        self.assertEqual(Decimal(fiscal['valor_total']), Decimal('350.00'))

    def test_painel_ignora_nfe_nao_realizada_e_bate_com_o_preco_da_aba_geral(self):
        produto = _produto('PNL-003')
        _entrada(
            produto,
            numero='EP-PNL-OK',
            data=date(2026, 9, 1),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('500.00'),
            quantidade=Decimal('2.000'),
        )
        _entrada(
            produto,
            numero='EP-PNL-REJEITADA',
            data=date(2026, 10, 5),
            status=NFeEntrada.StatusOperacional.REJEITADA,
            valor=Decimal('610.00'),
            quantidade=Decimal('2.000'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('500.00'))
        self.assertEqual(
            Decimal(painel['ultima_compra']['valor_unitario']),
            Decimal(str(ProdutoSerializer(produto).data['ultimo_preco_compra'])),
        )

    def test_sem_nfe_o_painel_e_a_aba_geral_mostram_o_mesmo_preco_do_pedido_de_compra(self):
        produto = _produto('PNL-004')
        _pedido_compra(
            produto,
            numero='PC-PNL-4',
            data=date(2026, 9, 30),
            status='PENDENTE',
            valor_unitario=Decimal('87.50'),
        )
        painel = montar_painel_resumo_produto(produto)
        self.assertEqual(painel['ultima_compra']['origem'], 'pedido_compra')
        self.assertEqual(Decimal(painel['ultima_compra']['valor_unitario']), Decimal('87.50'))
        self.assertEqual(
            Decimal(painel['ultima_compra']['valor_unitario']),
            Decimal(str(ProdutoSerializer(produto).data['ultimo_preco_compra'])),
        )

    def test_inteligencia_de_preco_usa_o_unitario_real_da_linha(self):
        produto = _produto('PNL-005')
        _entrada(
            produto,
            numero='EP-PNL-5',
            data=date(2026, 9, 10),
            status=NFeEntrada.StatusOperacional.AUTORIZADA_PRODUCAO,
            valor=Decimal('900.00'),
            quantidade=Decimal('8.000'),
        )
        inteligencia = montar_painel_resumo_produto(produto)['inteligencia_compras']
        self.assertEqual(Decimal(inteligencia['menor_preco']), Decimal('900.00'))
        self.assertEqual(Decimal(inteligencia['maior_preco']), Decimal('900.00'))
