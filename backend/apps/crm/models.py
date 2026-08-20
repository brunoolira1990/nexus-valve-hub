from decimal import Decimal

from django.db import models
from django.db.models import Q

from apps.cadastros.models import Cliente, Colaborador
from apps.cadastros.utils import normalizar_cnpj


class Lead(models.Model):
    class Status(models.TextChoices):
        NOVO = 'NOVO', 'Novo'
        QUALIFICANDO = 'QUALIFICANDO', 'Em qualificação'
        CONVERTIDO = 'CONVERTIDO', 'Convertido'
        DESCARTADO = 'DESCARTADO', 'Descartado'

    class Origem(models.TextChoices):
        INDICACAO = 'INDICACAO', 'Indicação'
        SITE = 'SITE', 'Site'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'
        TELEFONE = 'TELEFONE', 'Telefone'
        EVENTO = 'EVENTO', 'Evento'
        OUTRA = 'OUTRA', 'Outra'

    nome = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=20, blank=True)
    nome_contato = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=64, blank=True)
    cidade = models.CharField(max_length=128, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.OUTRA)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOVO)
    responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_crm',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_crm',
    )
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']
        verbose_name = 'Lead CRM'
        verbose_name_plural = 'Leads CRM'
        indexes = [
            models.Index(fields=['status', '-atualizado_em'], name='crm_lead_status_upd_idx'),
            models.Index(fields=['responsavel', 'status'], name='crm_lead_resp_status_idx'),
            models.Index(fields=['-atualizado_em', '-id'], name='crm_lead_updated_id_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['cnpj'],
                condition=Q(cnpj__gt=''),
                name='crm_lead_cnpj_unique_nonblank',
            ),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.cnpj = normalizar_cnpj(self.cnpj or '')
        self.uf = (self.uf or '').strip().upper()
        super().save(*args, **kwargs)


class Oportunidade(models.Model):
    class Status(models.TextChoices):
        ABERTA = 'ABERTA', 'Aberta'
        GANHA = 'GANHA', 'Ganha'
        PERDIDA = 'PERDIDA', 'Perdida'

    class Etapa(models.TextChoices):
        QUALIFICACAO = 'QUALIFICACAO', 'Qualificação'
        ESPECIFICACAO = 'ESPECIFICACAO', 'Especificação técnica'
        PROPOSTA = 'PROPOSTA', 'Proposta'
        NEGOCIACAO = 'NEGOCIACAO', 'Negociação'
        FECHAMENTO = 'FECHAMENTO', 'Fechamento'

    titulo = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTA)
    etapa = models.CharField(max_length=20, choices=Etapa.choices, default=Etapa.QUALIFICACAO)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oportunidades',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oportunidades_crm',
    )
    responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oportunidades_crm',
    )
    valor_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    probabilidade = models.PositiveSmallIntegerField(default=0)
    previsao_fechamento = models.DateField(null=True, blank=True)
    proxima_acao = models.DateField(null=True, blank=True)
    motivo_perda = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']
        verbose_name = 'Oportunidade CRM'
        verbose_name_plural = 'Oportunidades CRM'
        indexes = [
            models.Index(fields=['status', 'etapa', '-atualizado_em'], name='crm_opp_status_stage_idx'),
            models.Index(fields=['responsavel', 'status', 'proxima_acao'], name='crm_opp_resp_action_idx'),
            models.Index(fields=['previsao_fechamento', 'status'], name='crm_opp_forecast_status_idx'),
            models.Index(fields=['-atualizado_em', '-id'], name='crm_opp_updated_id_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(probabilidade__gte=0) & Q(probabilidade__lte=100),
                name='crm_opp_probability_0_100',
            ),
        ]

    def __str__(self):
        return self.titulo
