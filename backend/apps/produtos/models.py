from decimal import Decimal

from django.db import models


def _norm_polegada(polegada: str) -> str:
    return (polegada or '').replace('"', '')


class Ncm(models.Model):
    codigo = models.CharField(max_length=16, unique=True)
    descricao = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'NCM'

    def __str__(self):
        return self.codigo


class Polegada(models.Model):
    codigo = models.CharField(max_length=4, unique=True)
    descricao = models.CharField(max_length=64)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Polegada'

    def __str__(self):
        return f'{self.codigo} — {self.descricao}'


class Produto(models.Model):
    figura = models.CharField(max_length=32)
    sufixo = models.CharField(max_length=32)
    schedule = models.CharField(max_length=32)
    polegada_principal = models.CharField(max_length=32)
    polegada_secundaria = models.CharField(max_length=32, blank=True)
    descricao = models.CharField(max_length=512)
    material = models.CharField(max_length=128, blank=True)
    tipo_peca = models.CharField(max_length=128, blank=True)
    pressao_nominal = models.CharField(max_length=64, blank=True)
    norma = models.CharField(max_length=128, blank=True)
    conexao = models.CharField(max_length=128, blank=True)
    ncm = models.CharField(max_length=16, blank=True)
    preco_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    preco_venda = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    estoque_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    codigo_completo = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ['codigo_completo']

    def gerar_codigo_completo(self) -> str:
        p1 = _norm_polegada(self.polegada_principal)
        p2 = _norm_polegada(self.polegada_secundaria)
        if p2:
            sufixo_polegada = f'{p1}x{p2}'
        else:
            sufixo_polegada = p1
        return f'{self.figura}.{self.sufixo}.{self.schedule}.{sufixo_polegada}'

    def save(self, *args, **kwargs):
        self.codigo_completo = self.gerar_codigo_completo()
        super().save(*args, **kwargs)
