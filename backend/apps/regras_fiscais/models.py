from django.db import models


class RegraFiscal(models.Model):
    class Operacao(models.TextChoices):
        ENTRADA = 'Entrada', 'Entrada'
        SAIDA = 'Saída', 'Saída'

    ncm = models.CharField(max_length=16)
    uf_origem = models.CharField(max_length=2)
    uf_destino = models.CharField(max_length=2)
    operacao = models.CharField(max_length=16, choices=Operacao.choices)
    cfop = models.CharField(max_length=8)
    cst_icms = models.CharField(max_length=8, blank=True)
    aliquota_icms = models.FloatField(default=0)
    cst_pis = models.CharField(max_length=8, blank=True)
    aliquota_pis = models.FloatField(default=0)
    cst_cofins = models.CharField(max_length=8, blank=True)
    aliquota_cofins = models.FloatField(default=0)
    cst_ipi = models.CharField(max_length=8, blank=True)
    aliquota_ipi = models.FloatField(default=0)
    base_calculo = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['ncm', 'uf_origem', 'uf_destino']
        indexes = [
            models.Index(fields=['ncm', 'uf_origem', 'uf_destino', 'operacao']),
        ]

    def __str__(self):
        return f'{self.ncm} {self.uf_origem}->{self.uf_destino} {self.operacao}'
