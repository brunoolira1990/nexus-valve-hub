from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.db import models


class EstoqueCorrida(models.Model):
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE, related_name='estoques_corrida')
    corrida = models.ForeignKey('corridas.Corrida', on_delete=models.CASCADE, related_name='estoques')
    saldo = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))

    class Meta:
        unique_together = [['produto', 'corrida']]
        ordering = ['produto_id', 'corrida_id']


class NFeEntrada(models.Model):
    numero = models.CharField(max_length=64)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        related_name='nf_entradas',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas',
    )
    cte = models.ForeignKey(
        'fiscal.CTeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas_vinculadas',
    )

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF entrada'


class ItemNFeEntrada(models.Model):
    nf = models.ForeignKey(NFeEntrada, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )


class NFeSaida(models.Model):
    numero = models.CharField(max_length=64)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='nf_saidas',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=64, blank=True)
    pedido_venda = models.ForeignKey(
        'comercial.PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas',
    )

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF saída'


class ItemNFeSaida(models.Model):
    nf = models.ForeignKey(NFeSaida, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )


class CTeEntrada(models.Model):
    numero = models.CharField(max_length=64, unique=True)
    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.PROTECT,
        related_name='ctes',
    )
    tomador = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='ctes_como_tomador',
    )
    valor_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    data = models.DateField()
    nfe_ids = ArrayField(models.IntegerField(), default=list, blank=True)

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'CT-e entrada'
