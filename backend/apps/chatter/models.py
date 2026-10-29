from django.conf import settings
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
