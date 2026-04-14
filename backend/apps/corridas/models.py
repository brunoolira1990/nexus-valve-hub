from django.db import models


class Corrida(models.Model):
    numero = models.CharField(max_length=64, unique=True)
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.PROTECT,
        related_name='corridas',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        related_name='corridas',
    )
    data_recebimento = models.DateField()
    nf_entrada = models.CharField(max_length=64, blank=True)
    composicao_quimica = models.JSONField(default=dict)
    tracao = models.JSONField(default=dict)
    impacto = models.JSONField(default=dict)

    class Meta:
        ordering = ['-data_recebimento', 'numero']

    def __str__(self):
        return self.numero
