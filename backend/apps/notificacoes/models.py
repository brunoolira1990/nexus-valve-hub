from django.conf import settings
from django.db import models
from django.db.models import Q


class Notificacao(models.Model):
    class Modulo(models.TextChoices):
        COMERCIAL = 'COMERCIAL', 'Comercial'
        FISCAL = 'FISCAL', 'Fiscal'
        FINANCEIRO = 'FINANCEIRO', 'Financeiro'
        ESTOQUE = 'ESTOQUE', 'Estoque'
        QUALIDADE = 'QUALIDADE', 'Qualidade'
        COMPRAS = 'COMPRAS', 'Compras'
        CADASTROS = 'CADASTROS', 'Cadastros'
        ATENDIMENTOS = 'ATENDIMENTOS', 'Atendimentos'
        CRM = 'CRM', 'CRM'
        SISTEMA = 'SISTEMA', 'Sistema'

    class Prioridade(models.TextChoices):
        BAIXA = 'BAIXA', 'Baixa'
        NORMAL = 'NORMAL', 'Normal'
        ALTA = 'ALTA', 'Alta'
        CRITICA = 'CRITICA', 'Crítica'

    class Tipo(models.TextChoices):
        NOVO_LEAD = 'NOVO_LEAD', 'Novo lead'
        ATIVIDADE_VENCIDA = 'ATIVIDADE_VENCIDA', 'Atividade vencida'
        TITULO_VENCIDO = 'TITULO_VENCIDO', 'Título financeiro vencido'
        ESTOQUE_MINIMO = 'ESTOQUE_MINIMO', 'Estoque abaixo do mínimo'
        PROPOSTA_ACAO = 'PROPOSTA_ACAO', 'Proposta aguardando ação'
        PENDENCIA_OPERACIONAL = 'PENDENCIA_OPERACIONAL', 'Pendência operacional'
        DOCUMENTO_FISCAL = 'DOCUMENTO_FISCAL', 'Documento fiscal'
        SISTEMA = 'SISTEMA', 'Aviso do sistema'

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificacoes',
    )
    modulo = models.CharField(max_length=20, choices=Modulo.choices, default=Modulo.SISTEMA, db_index=True)
    tipo = models.CharField(max_length=32, choices=Tipo.choices, default=Tipo.SISTEMA, db_index=True)
    prioridade = models.CharField(
        max_length=10,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
        db_index=True,
    )
    titulo = models.CharField(max_length=180)
    mensagem = models.TextField()
    url_destino = models.CharField(max_length=500, blank=True)
    objeto_tipo = models.CharField(max_length=80, blank=True)
    objeto_id = models.CharField(max_length=80, blank=True)
    chave_idempotencia = models.CharField(max_length=180, blank=True)
    lida = models.BooleanField(default=False, db_index=True)
    arquivada = models.BooleanField(default=False, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    arquivada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        indexes = [
            models.Index(
                fields=['destinatario', 'arquivada', '-criado_em'],
                name='notif_recipient_archive_idx',
            ),
            models.Index(
                fields=['destinatario', 'lida', 'arquivada'],
                name='notif_recipient_read_idx',
            ),
            models.Index(
                fields=['tipo', 'objeto_tipo', 'objeto_id'],
                name='notif_type_object_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['destinatario', 'chave_idempotencia'],
                condition=Q(chave_idempotencia__gt=''),
                name='notif_recipient_idempotency_uniq',
            ),
        ]

    def __str__(self):
        return self.titulo
