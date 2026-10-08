from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    """Histórico append-only de alterações de campos (MVP Cliente/Produto)."""

    class Operacao(models.TextChoices):
        CREATE = 'CREATE', 'Criação'
        UPDATE = 'UPDATE', 'Atualização'

    app_label = models.CharField(max_length=64, db_index=True)
    model_name = models.CharField(max_length=64, db_index=True)
    object_id = models.PositiveBigIntegerField(db_index=True)
    operacao = models.CharField(max_length=16, choices=Operacao.choices)
    alteracoes = models.JSONField(default=dict)
    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_auditoria',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Registro de auditoria'
        verbose_name_plural = 'Registros de auditoria'
        # Append-only: não gerar add/change/delete no auth.
        default_permissions = ('view',)
        indexes = [
            models.Index(
                fields=['app_label', 'model_name', 'object_id'],
                name='auditoria_obj_lookup_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.app_label}.{self.model_name}#{self.object_id} {self.operacao}'
