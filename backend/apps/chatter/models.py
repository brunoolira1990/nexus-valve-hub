from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models


class NotaChatter(models.Model):
    """Nota interna anexada a qualquer entidade pelo par (entity_type, entity_id).

    Chave polimórfica sem GenericForeignKey, igual a RegistroAuditoria: a nota
    sobrevive à exclusão da entidade e não exige tabela de junção por módulo.
    """

    entity_type = models.CharField(max_length=32, db_index=True)
    entity_id = models.PositiveBigIntegerField(db_index=True)
    texto = models.TextField()
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_chatter',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Nota interna'
        verbose_name_plural = 'Notas internas'
        indexes = [
            models.Index(
                fields=['entity_type', 'entity_id', '-criado_em'],
                name='chatter_entity_timeline_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.entity_type}#{self.entity_id}: {self.texto[:60]}'

    def delete(self, using=None, keep_parents=False):
        # O CASCADE dos anexos é resolvido em SQL e não passa por AnexoChatter.delete(),
        # então os arquivos precisam ser listados antes da sentença de exclusão.
        nomes = list(self.anexos.exclude(arquivo='').values_list('arquivo', flat=True))
        super().delete(using=using, keep_parents=keep_parents)
        for nome in nomes:
            default_storage.delete(nome)


class AnexoChatter(models.Model):
    """Arquivo enviado junto a uma nota interna."""

    nota = models.ForeignKey(
        NotaChatter,
        on_delete=models.CASCADE,
        related_name='anexos',
    )
    arquivo = models.FileField(upload_to='chatter/anexos/%Y/%m/')
    nome_original = models.CharField(max_length=255)
    tamanho_bytes = models.PositiveBigIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Anexo de nota'
        verbose_name_plural = 'Anexos de nota'

    def __str__(self) -> str:
        return f'{self.nome_original} ({self.tamanho_bytes} bytes)'

    def delete(self, using=None, keep_parents=False):
        nome = self.arquivo.name if self.arquivo else None
        super().delete(using=using, keep_parents=keep_parents)
        if nome:
            default_storage.delete(nome)
