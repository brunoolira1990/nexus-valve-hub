from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.db import models


def _default_dias_parcelas():
    return []


def _default_datas():
    return []


class Proposta(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='propostas',
        null=True,
        blank=True,
    )
    cliente_avulso_nome = models.CharField(max_length=255, blank=True)
    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='propostas_emitidas',
        null=True,
        blank=True,
    )
    uf_origem = models.CharField(
        max_length=2,
        blank=True,
        help_text='Denormalizado a partir da UF da empresa emitente (uso em regra fiscal).',
    )
    uf_destino_avulso = models.CharField(
        max_length=2,
        blank=True,
        help_text='UF destino quando o cliente é avulso (sem cadastro com UF).',
    )
    operacao_fiscal = models.CharField(
        max_length=16,
        default='Saída',
        help_text='Fluxo comercial: sempre saída; preenchido automaticamente.',
    )
    data = models.DateField()
    validade = models.DateField()
    vendedor = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_previstos = ArrayField(models.DateField(), default=_default_datas, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['-data', 'numero']


class ItemProposta(models.Model):
    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT, null=True, blank=True)
    descricao_avulsa = models.CharField(max_length=255, blank=True)
    ncm_avulso = models.CharField(
        max_length=16,
        blank=True,
        help_text='NCM informado manualmente quando o item não possui produto cadastrado (regra fiscal).',
    )
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    unidade_negociada = models.CharField(max_length=16, blank=True)
    quantidade_negociada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    preco_por_unidade_negociada = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_kg = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_metro = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    custo_utilizado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    despesas = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    ipi_entrada_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    ipi_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    st_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    outros_impostos_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    custo_final = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    icms_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    pis_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    cofins_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    ipi_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    regra_fiscal_id = models.PositiveIntegerField(null=True, blank=True)
    irpj_estimado_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    csll_estimada_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    comissao_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    frete_saida = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    outras_despesas_saida = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    modo_preco = models.CharField(max_length=16, default='sugerido')
    preco_sugerido = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    preco_final = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    margem_resultante = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    lucro_resultante = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    snapshot_produto = models.JSONField(default=dict, blank=True)


class PedidoVenda(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='pedidos_venda_emitidos',
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='pedidos_venda',
    )
    data = models.DateField()
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_previstos = ArrayField(models.DateField(), default=_default_datas, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_gerados',
    )

    class Meta:
        ordering = ['-data', 'numero']


class ItemPedidoVenda(models.Model):
    pedido = models.ForeignKey(PedidoVenda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    unidade_negociada = models.CharField(max_length=16, blank=True)
    quantidade_negociada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    preco_por_unidade_negociada = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_kg = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_metro = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    snapshot_produto = models.JSONField(default=dict, blank=True)


class PedidoCompra(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        related_name='pedidos_compra',
    )
    data = models.DateField()
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_previstos = ArrayField(models.DateField(), default=_default_datas, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['-data', 'numero']


class ItemPedidoCompra(models.Model):
    pedido = models.ForeignKey(PedidoCompra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    unidade_negociada = models.CharField(max_length=16, blank=True)
    quantidade_negociada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    preco_por_unidade_negociada = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_kg = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_metro = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    snapshot_produto = models.JSONField(default=dict, blank=True)
