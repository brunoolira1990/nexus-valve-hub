from decimal import Decimal

from django.db import models


class PlanoConta(models.Model):
    codigo = models.CharField(max_length=32)
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=64, blank=True)
    pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='filhos',
    )

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Plano de contas'
        verbose_name_plural = 'Plano de contas'

    def __str__(self):
        return f'{self.codigo} {self.nome}'


class Lancamento(models.Model):
    class Tipo(models.TextChoices):
        DEBITO = 'D', 'Débito'
        CREDITO = 'C', 'Crédito'

    conta = models.ForeignKey(PlanoConta, on_delete=models.PROTECT, related_name='lancamentos')
    data = models.DateField()
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    historico = models.CharField(max_length=512, blank=True)
    tipo = models.CharField(max_length=1, choices=Tipo.choices)

    class Meta:
        ordering = ['-data', 'id']
