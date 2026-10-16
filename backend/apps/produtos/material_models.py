"""Model Material — cadastro mestre de materiais de engenharia.

Separado de models.py para não sobrecarregar o arquivo principal.
Importado em models.py via:  from apps.produtos.material_models import Material
"""

from __future__ import annotations

from django.db import models


class Material(models.Model):
    """Cadastro mestre de materiais (aços, não-ferrosos, polímeros, etc.).

    Substitui o campo CharField livre `Produto.material`.
    A migração de dados é feita em outra fase — este model é somente leitura
    para Produto/FamiliaProduto por enquanto.
    """

    class Categoria(models.TextChoices):
        ACO_CARBONO   = 'ACO_CARBONO',   'Aço Carbono'
        ACO_INOX      = 'ACO_INOX',      'Aço Inox'
        FERRO_FUNDIDO = 'FERRO_FUNDIDO', 'Ferro Fundido'
        ACO_LIGA      = 'ACO_LIGA',      'Aço Liga'
        NAO_FERROSO   = 'NAO_FERROSO',   'Não-ferroso'
        POLIMERO      = 'POLIMERO',      'Polímero'
        OUTRO         = 'OUTRO',         'Outro'

    # ------------------------------------------------------------------
    # Campos
    # ------------------------------------------------------------------
    codigo = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name='Código',
        help_text='Gerado automaticamente: MAT-0001, MAT-0002 …',
    )
    nome = models.CharField(
        max_length=120,
        unique=True,
        verbose_name='Nome completo',
        help_text='Exemplo: Aço Carbono A105',
    )
    nome_curto = models.CharField(
        max_length=60,
        verbose_name='Nome curto',
        help_text='Rótulo compacto para UI: A105, WCB, 316L …',
    )
    categoria = models.CharField(
        max_length=20,
        choices=Categoria.choices,
        verbose_name='Categoria',
        db_index=True,
    )
    norma_astm = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Norma / especificação',
        help_text='Exemplo: ASTM A105, DIN GG25, NBR 6590',
    )
    ncm_sugerido = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='NCM sugerido',
        help_text='Apenas orientação — o NCM real é definido no produto/família.',
    )
    densidade_kg_m3 = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Densidade (kg/m³)',
    )
    aliases = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Aliases / sinônimos',
        help_text='Lista de strings para busca e correspondência: ["WCB", "A-216 WCB"]',
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        db_index=True,
    )
    ordem = models.PositiveIntegerField(
        default=100,
        verbose_name='Ordem de exibição',
        help_text='Menor número aparece primeiro nas listas.',
    )
    criado_em  = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------
    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'Material'
        verbose_name_plural = 'Materiais'

    # ------------------------------------------------------------------
    # Métodos
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gera MAT-XXXX a partir do maior ID existente + 1.
            # Simples e sem race condition para o volume esperado (<10k registros).
            ultimo = Material.objects.order_by('-id').values_list('id', flat=True).first()
            proximo = (ultimo + 1) if ultimo is not None else 1
            self.codigo = f'MAT-{proximo:04d}'
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.codigo} — {self.nome}'
