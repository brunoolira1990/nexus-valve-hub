from decimal import Decimal

from django.db import models


class Proposta(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='propostas',
    )
    data = models.DateField()
    validade = models.DateField()
    vendedor = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=64, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['-data', 'numero']


class ItemProposta(models.Model):
    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))


class PedidoVenda(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='pedidos_venda',
    )
    data = models.DateField()
    status = models.CharField(max_length=64, blank=True)
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
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )


class PedidoCompra(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        related_name='pedidos_compra',
    )
    data = models.DateField()
    status = models.CharField(max_length=64, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['-data', 'numero']


class ItemPedidoCompra(models.Model):
    pedido = models.ForeignKey(PedidoCompra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
