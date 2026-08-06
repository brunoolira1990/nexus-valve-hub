"""Persistência de apuração fiscal (F1) — rascunho, fechamento e auditoria."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ApuracaoFiscal(models.Model):
    """Cabeçalho de apuração por empresa + período (competência)."""

    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        FECHADO = 'FECHADO', 'Fechado'

    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='apuracoes_fiscais',
    )
    data_inicio = models.DateField(db_index=True)
    data_fim = models.DateField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )
    tipo = models.CharField(max_length=16, default='AMBOS')  # ENTRADA|SAIDA|AMBOS
    fonte = models.CharField(max_length=16, default='TODOS')  # TODOS|OPERACIONAIS|HISTORICOS

    # Totais principais (snapshot no fechar / preview no rascunho)
    valor_entradas = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_saidas = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    icms_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    icms_credito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    icms_st_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    difal_valor = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    ipi_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    ipi_credito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    pis_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    pis_credito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    cofins_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    cofins_credito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    saldo_icms = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    totais_json = models.JSONField(default=dict, blank=True)
    filtros_json = models.JSONField(default=dict, blank=True)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    versao_api_apuracao = models.CharField(max_length=32, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apuracoes_fiscais_criadas',
    )
    fechado_em = models.DateTimeField(null=True, blank=True)
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apuracoes_fiscais_fechadas',
    )

    class Meta:
        ordering = ['-data_inicio', '-id']
        verbose_name = 'Apuração fiscal'
        verbose_name_plural = 'Apurações fiscais'
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'data_inicio', 'data_fim'],
                name='apuracao_fiscal_empresa_periodo_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['empresa', 'status', 'data_inicio'], name='apuracao_emp_st_ini_idx'),
        ]

    def __str__(self) -> str:
        return (
            f'Apuração #{self.pk} emp={self.empresa_id} '
            f'{self.data_inicio}→{self.data_fim} [{self.status}]'
        )

    @property
    def esta_fechada(self) -> bool:
        return self.status == self.Status.FECHADO


class ApuracaoItem(models.Model):
    """Item consolidado da apuração (agrupamento ou origem documental)."""

    class Lado(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada'
        SAIDA = 'SAIDA', 'Saída'
        AMBOS = 'AMBOS', 'Ambos'

    class OrigemTipo(models.TextChoices):
        AGRUPAMENTO_CFOP = 'AGRUPAMENTO_CFOP', 'Agrupamento CFOP'
        AGRUPAMENTO_NCM = 'AGRUPAMENTO_NCM', 'Agrupamento NCM'
        NFE_ENTRADA_HIST = 'NFE_ENTRADA_HIST', 'NF-e entrada histórica'
        NFE_SAIDA_HIST = 'NFE_SAIDA_HIST', 'NF-e saída histórica'
        NFE_ENTRADA = 'NFE_ENTRADA', 'NF-e entrada operacional'
        NFE_SAIDA = 'NFE_SAIDA', 'NF-e saída operacional'
        CTE = 'CTE', 'CT-e'
        OUTRO = 'OUTRO', 'Outro'

    apuracao = models.ForeignKey(
        ApuracaoFiscal,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    lado = models.CharField(max_length=16, choices=Lado.choices, default=Lado.AMBOS)
    origem_tipo = models.CharField(
        max_length=32,
        choices=OrigemTipo.choices,
        default=OrigemTipo.AGRUPAMENTO_CFOP,
    )
    origem_documento_id = models.PositiveBigIntegerField(null=True, blank=True)
    origem_item_id = models.PositiveBigIntegerField(null=True, blank=True)
    chave = models.CharField(max_length=128, blank=True, db_index=True)

    cfop = models.CharField(max_length=8, blank=True)
    ncm = models.CharField(max_length=16, blank=True)
    cst_icms = models.CharField(max_length=8, blank=True)
    cst_pis = models.CharField(max_length=8, blank=True)
    cst_cofins = models.CharField(max_length=8, blank=True)

    quantidade_itens = models.PositiveIntegerField(default=0)
    valor_produtos = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    base_icms = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_icms = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    base_icms_st = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_icms_st = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_fcp_st = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_icms_uf_dest = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    base_ipi = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_ipi = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    base_pis = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_pis = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    base_cofins = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_cofins = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    detalhe_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Item de apuração'
        verbose_name_plural = 'Itens de apuração'
        indexes = [
            models.Index(fields=['apuracao', 'cfop'], name='apuracao_item_cfop_idx'),
        ]

    def __str__(self) -> str:
        return f'Item apuração={self.apuracao_id} {self.origem_tipo}:{self.chave or self.cfop}'


class LogsAuditoriaApuracao(models.Model):
    """Trilha append-only de ações sobre ApuracaoFiscal."""

    class Acao(models.TextChoices):
        ABRIU = 'ABRIU', 'Abriu rascunho'
        FECHOU = 'FECHOU', 'Fechou período'
        REABRIU = 'REABRIU', 'Reabriu período'
        AJUSTE_ADICIONADO = 'AJUSTE_ADICIONADO', 'Ajuste adicionado'
        AJUSTE_REMOVIDO = 'AJUSTE_REMOVIDO', 'Ajuste removido'
        ATUALIZOU_RASCUNHO = 'ATUALIZOU_RASCUNHO', 'Atualizou rascunho'

    apuracao = models.ForeignKey(
        ApuracaoFiscal,
        on_delete=models.CASCADE,
        related_name='logs_auditoria',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_auditoria_apuracao',
    )
    acao = models.CharField(max_length=32, choices=Acao.choices, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    detalhe = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp', '-id']
        verbose_name = 'Log de auditoria da apuração'
        verbose_name_plural = 'Logs de auditoria da apuração'
        default_permissions = ('view',)  # append-only

    def __str__(self) -> str:
        return f'{self.acao} apuração={self.apuracao_id} @ {self.timestamp}'


class ApuracaoAjusteManual(models.Model):
    """Ajuste fiscal manual sobre apuração em RASCUNHO (F2)."""

    class Tipo(models.TextChoices):
        DEBITO = 'DEBITO', 'Débito'
        CREDITO = 'CREDITO', 'Crédito'
        ESTORNO = 'ESTORNO', 'Estorno'

    apuracao = models.ForeignKey(
        ApuracaoFiscal,
        on_delete=models.CASCADE,
        related_name='ajustes_manuais',
    )
    tipo = models.CharField(max_length=16, choices=Tipo.choices, db_index=True)
    valor = models.DecimalField(max_digits=16, decimal_places=2)
    motivo = models.CharField(max_length=500)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajustes_manuais_apuracao',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Ajuste manual de apuração'
        verbose_name_plural = 'Ajustes manuais de apuração'
        indexes = [
            models.Index(fields=['apuracao', 'tipo'], name='apuracao_ajuste_tipo_idx'),
        ]

    def __str__(self) -> str:
        return f'Ajuste #{self.pk} {self.tipo} {self.valor} apuração={self.apuracao_id}'

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        motivo = (self.motivo or '').strip()
        if len(motivo) < 5:
            raise ValidationError({'motivo': 'Motivo obrigatório com pelo menos 5 caracteres.'})
        if self.valor is None or self.valor <= 0:
            raise ValidationError({'valor': 'Valor deve ser maior que zero.'})


class ApuracaoReforma(models.Model):
    """Snapshot CBS/IBS/IS da reforma tributária no fechamento (F3)."""

    apuracao = models.OneToOneField(
        ApuracaoFiscal,
        on_delete=models.CASCADE,
        related_name='reforma',
    )
    cbs_credito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    cbs_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    ibs_credito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    ibs_debito = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    is_valor = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    detalhe_json = models.JSONField(default=dict, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Apuração reforma tributária'
        verbose_name_plural = 'Apurações reforma tributária'

    def __str__(self) -> str:
        return f'Reforma apuração={self.apuracao_id} CBS D={self.cbs_debito} C={self.cbs_credito}'
