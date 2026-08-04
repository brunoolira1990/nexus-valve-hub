from django.db import models


class Corrida(models.Model):
    # Mesmo nº de corrida/heat pode existir em produtos diferentes (comum em mill certificates).
    # A unicidade é por produto + número — não global só pelo número.
    numero = models.CharField(max_length=64, db_index=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=['numero', 'produto'],
                name='corridas_corrida_numero_produto_uniq',
            ),
        ]

    def __str__(self):
        return self.numero
