"""Modelos financeiros operacionais — ERP 4.0.14."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro
from apps.financeiro.status import calcular_status_titulo


class ContaFinanceira(models.Model):
    class Tipo(models.TextChoices):
        CAIXA = 'CAIXA', 'Caixa'
        BANCO = 'BANCO', 'Banco'
        CARTEIRA = 'CARTEIRA', 'Carteira'
        OUTRO = 'OUTRO', 'Outro'

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=16, choices=Tipo.choices, default=Tipo.CAIXA)
    banco = models.CharField(max_length=120, blank=True)
    agencia = models.CharField(max_length=32, blank=True)
    conta = models.CharField(max_length=32, blank=True)
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Conta financeira'
        verbose_name_plural = 'Contas financeiras'

    def __str__(self) -> str:
        return self.nome


class CategoriaFinanceira(models.Model):
    class Tipo(models.TextChoices):
        RECEITA = 'RECEITA', 'Receita'
        DESPESA = 'DESPESA', 'Despesa'
        AMBOS = 'AMBOS', 'Ambos'

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.AMBOS)
    categoria_pai = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='filhas',
    )
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name_plural = 'Categorias financeiras'

    def __str__(self) -> str:
        return self.nome


class CentroCusto(models.Model):
    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name_plural = 'Centros de custo'

    def __str__(self) -> str:
        return self.nome


class TituloFinanceiro(models.Model):
    class Tipo(models.TextChoices):
        RECEBER = 'RECEBER', 'Conta a receber'
        PAGAR = 'PAGAR', 'Conta a pagar'

    class OrigemTipo(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        PEDIDO_VENDA = 'PEDIDO_VENDA', 'Pedido de Venda'
        FATURAMENTO = 'FATURAMENTO', 'Faturamento'
        NFE_SAIDA = 'NFE_SAIDA', 'NF-e Saída'
        PEDIDO_COMPRA = 'PEDIDO_COMPRA', 'Pedido de Compra'
        NFE_ENTRADA = 'NFE_ENTRADA', 'NF-e Entrada'
        SERVICO = 'SERVICO', 'Serviço'
        AJUSTE = 'AJUSTE', 'Ajuste manual'
        IMPORTACAO = 'IMPORTACAO', 'Importação futura'
        APURACAO_FISCAL = 'APURACAO_FISCAL', 'Apuração fiscal (futuro)'

    class TipoLancamentoPagar(models.TextChoices):
        FORNECEDOR = 'FORNECEDOR', 'Fornecedor'
        DESPESA_OPERACIONAL = 'DESPESA_OPERACIONAL', 'Despesa operacional'
        SERVICO = 'SERVICO', 'Serviço'
        TRIBUTO_IMPOSTO = 'TRIBUTO_IMPOSTO', 'Tributo / Imposto'
        OUTROS = 'OUTROS', 'Outros'

    class TipoTributo(models.TextChoices):
        ICMS = 'ICMS', 'ICMS'
        PIS = 'PIS', 'PIS'
        COFINS = 'COFINS', 'COFINS'
        IPI = 'IPI', 'IPI'
        ISS = 'ISS', 'ISS'
        IBS = 'IBS', 'IBS'
        CBS = 'CBS', 'CBS'
        IR = 'IR', 'IR'
        CSLL = 'CSLL', 'CSLL'
        INSS = 'INSS', 'INSS'
        FGTS = 'FGTS', 'FGTS'
        OUTROS = 'OUTROS', 'Outros'

    class Status(models.TextChoices):
        EM_ABERTO = 'EM_ABERTO', 'Em aberto'
        VENCIDO = 'VENCIDO', 'Vencido'
        PARCIALMENTE_RECEBIDO = 'PARCIALMENTE_RECEBIDO', 'Parcialmente recebido'
        RECEBIDO = 'RECEBIDO', 'Recebido'
        PARCIALMENTE_PAGO = 'PARCIALMENTE_PAGO', 'Parcialmente pago'
        PAGO = 'PAGO', 'Pago'
        CANCELADO = 'CANCELADO', 'Cancelado'

    tipo = models.CharField(max_length=12, choices=Tipo.choices, db_index=True)
    numero = models.CharField(max_length=40, db_index=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='titulos_financeiros',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='titulos_financeiros',
    )
    tipo_lancamento = models.CharField(
        max_length=24,
        choices=TipoLancamentoPagar.choices,
        blank=True,
        db_index=True,
    )
    descricao = models.CharField(max_length=255, blank=True)
    competencia = models.DateField(null=True, blank=True, help_text='Competência (ex.: primeiro dia do mês)')
    tipo_tributo = models.CharField(
        max_length=16,
        choices=TipoTributo.choices,
        blank=True,
        db_index=True,
    )
    periodo_apuracao = models.CharField(max_length=80, blank=True)
    numero_guia = models.CharField(max_length=80, blank=True)
    codigo_receita = models.CharField(max_length=40, blank=True)
    documento_origem = models.CharField(max_length=80, blank=True)
    origem_tipo = models.CharField(
        max_length=20,
        choices=OrigemTipo.choices,
        default=OrigemTipo.MANUAL,
        db_index=True,
    )
    origem_id = models.PositiveIntegerField(null=True, blank=True)
    origem_descricao = models.CharField(max_length=255, blank=True)
    origem_numero = models.CharField(max_length=80, blank=True)
    origem_data = models.DateField(null=True, blank=True)
    data_emissao = models.DateField()
    data_vencimento = models.DateField(db_index=True)
    valor_original = models.DecimalField(max_digits=14, decimal_places=2)
    valor_aberto = models.DecimalField(max_digits=14, decimal_places=2)
    valor_baixado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.EM_ABERTO, db_index=True)
    forma_pagamento_prevista_codigo = models.CharField(
        max_length=32,
        choices=FormaPagamentoCodigo.CHOICES,
        blank=True,
    )
    conta_financeira_prevista = models.ForeignKey(
        ContaFinanceira,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='titulos_previstos',
    )
    categoria = models.ForeignKey(
        CategoriaFinanceira,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='titulos',
    )
    centro_custo = models.ForeignKey(
        CentroCusto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='titulos',
    )
    observacoes = models.TextField(blank=True)
    cancelado = models.BooleanField(default=False)
    motivo_cancelamento = models.TextField(blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='titulos_financeiros_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_vencimento', '-pk']
        indexes = [
            models.Index(fields=['tipo', 'status']),
            models.Index(fields=['tipo', 'data_vencimento']),
        ]

    def __str__(self) -> str:
        return f'{self.numero} ({self.get_tipo_display()})'

    def recalcular_saldos_e_status(self, *, save: bool = True) -> None:
        from apps.financeiro.services.titulo import somar_baixas_titulo

        baixado = somar_baixas_titulo(self)
        self.valor_baixado = baixado
        self.valor_aberto = max(Decimal('0'), self.valor_original - baixado)
        self.status = calcular_status_titulo(
            tipo=self.tipo,
            valor_original=self.valor_original,
            valor_aberto=self.valor_aberto,
            valor_baixado=self.valor_baixado,
            data_vencimento=self.data_vencimento,
            cancelado=self.cancelado,
        )
        if save:
            self.save(
                update_fields=[
                    'valor_baixado',
                    'valor_aberto',
                    'status',
                    'atualizado_em',
                ],
            )

    @property
    def pode_editar_livremente(self) -> bool:
        if self.cancelado:
            return False
        return self.valor_baixado <= Decimal('0.01')

    @property
    def pode_baixar(self) -> bool:
        return not self.cancelado and self.valor_aberto > Decimal('0.01')


class ParcelaFinanceira(models.Model):
    titulo = models.ForeignKey(
        TituloFinanceiro,
        on_delete=models.CASCADE,
        related_name='parcelas',
    )
    numero_parcela = models.PositiveSmallIntegerField()
    data_vencimento = models.DateField()
    valor_original = models.DecimalField(max_digits=14, decimal_places=2)
    valor_aberto = models.DecimalField(max_digits=14, decimal_places=2)
    valor_baixado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=32, default=TituloFinanceiro.Status.EM_ABERTO)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['numero_parcela']
        unique_together = [('titulo', 'numero_parcela')]

    def __str__(self) -> str:
        return f'{self.titulo.numero}-{self.numero_parcela:03d}'

    def recalcular_saldos_e_status(self, *, save: bool = True) -> None:
        from apps.financeiro.services.parcela import somar_baixas_parcela

        baixado = somar_baixas_parcela(self)
        self.valor_baixado = baixado
        self.valor_aberto = max(Decimal('0'), self.valor_original - baixado)
        titulo = self.titulo
        self.status = calcular_status_titulo(
            tipo=titulo.tipo,
            valor_original=self.valor_original,
            valor_aberto=self.valor_aberto,
            valor_baixado=self.valor_baixado,
            data_vencimento=self.data_vencimento,
            cancelado=titulo.cancelado,
        )
        if save:
            self.save(update_fields=['valor_baixado', 'valor_aberto', 'status'])


class CreditoFinanceiro(models.Model):
    class Tipo(models.TextChoices):
        CLIENTE = 'CLIENTE', 'Cliente'
        FORNECEDOR = 'FORNECEDOR', 'Fornecedor'

    class Status(models.TextChoices):
        DISPONIVEL = 'DISPONIVEL', 'Disponível'
        PARCIALMENTE_UTILIZADO = 'PARCIALMENTE_UTILIZADO', 'Parcialmente utilizado'
        UTILIZADO = 'UTILIZADO', 'Utilizado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    class OrigemTipo(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        DEVOLUCAO = 'DEVOLUCAO', 'Devolução'
        AJUSTE = 'AJUSTE', 'Ajuste'
        PAGAMENTO_A_MAIOR = 'PAGAMENTO_A_MAIOR', 'Pagamento a maior'
        OUTROS = 'OUTROS', 'Outros'
        NFE_DEVOLUCAO_FUTURO = 'NFE_DEVOLUCAO_FUTURO', 'NF-e de devolução (futuro)'

    tipo = models.CharField(max_length=12, choices=Tipo.choices, db_index=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='creditos_financeiros',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='creditos_financeiros',
    )
    valor_original = models.DecimalField(max_digits=14, decimal_places=2)
    valor_utilizado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    saldo = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.DISPONIVEL,
        db_index=True,
    )
    origem_tipo = models.CharField(
        max_length=24,
        choices=OrigemTipo.choices,
        default=OrigemTipo.MANUAL,
    )
    origem_descricao = models.CharField(max_length=255, blank=True)
    origem_numero = models.CharField(max_length=80, blank=True)
    data_credito = models.DateField()
    motivo = models.CharField(max_length=255)
    observacoes = models.TextField(blank=True)
    cancelado = models.BooleanField(default=False)
    motivo_cancelamento = models.TextField(blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='creditos_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_credito', '-pk']
        indexes = [
            models.Index(fields=['tipo', 'status']),
            models.Index(fields=['cliente']),
            models.Index(fields=['fornecedor']),
        ]

    def __str__(self) -> str:
        return f'Crédito {self.pk} — R$ {self.saldo}'

    def recalcular_saldo_e_status(self, *, save: bool = True) -> None:
        from apps.financeiro.services.credito import somar_uso_credito

        if self.cancelado:
            self.status = self.Status.CANCELADO
        else:
            usado = somar_uso_credito(self)
            self.valor_utilizado = usado
            self.saldo = max(Decimal('0'), self.valor_original - usado)
            if self.saldo <= Decimal('0.01'):
                self.status = self.Status.UTILIZADO
            elif usado > Decimal('0.01'):
                self.status = self.Status.PARCIALMENTE_UTILIZADO
            else:
                self.status = self.Status.DISPONIVEL
        if save:
            self.save(update_fields=['valor_utilizado', 'saldo', 'status', 'atualizado_em'])

    @property
    def pode_aplicar(self) -> bool:
        return not self.cancelado and self.saldo > Decimal('0.01')


class BaixaFinanceira(models.Model):
    titulo = models.ForeignKey(
        TituloFinanceiro,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='baixas',
    )
    parcela = models.ForeignKey(
        ParcelaFinanceira,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='baixas',
    )
    credito = models.ForeignKey(
        CreditoFinanceiro,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimentos',
    )
    tipo_movimento = models.CharField(
        max_length=24,
        choices=TipoMovimentoFinanceiro.CHOICES,
        default=TipoMovimentoFinanceiro.AJUSTE_MANUAL,
        db_index=True,
    )
    forma_pagamento_codigo = models.CharField(
        max_length=40,
        choices=FormaPagamentoCodigo.CHOICES,
        default=FormaPagamentoCodigo.OUTROS,
        db_index=True,
    )
    data_baixa = models.DateField()
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    conta_financeira = models.ForeignKey(
        ContaFinanceira,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='baixas',
    )
    juros = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    multa = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    tarifa = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    observacoes = models.TextField(blank=True)
    estornada = models.BooleanField(default=False)
    motivo_estorno = models.TextField(blank=True)
    estornada_em = models.DateTimeField(null=True, blank=True)
    estornada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='baixas_estornadas',
    )
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='baixas_registradas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_baixa', '-pk']

    def __str__(self) -> str:
        return f'Movimento {self.valor} em {self.data_baixa}'


class FinanceiroEvento(models.Model):
    class Acao(models.TextChoices):
        CRIACAO = 'CRIACAO', 'Criação'
        EDICAO = 'EDICAO', 'Edição'
        BAIXA = 'BAIXA', 'Baixa'
        BAIXA_PARCIAL = 'BAIXA_PARCIAL', 'Baixa parcial'
        ESTORNO = 'ESTORNO', 'Estorno de baixa'
        CANCELAMENTO = 'CANCELAMENTO', 'Cancelamento'
        VENCIMENTO = 'VENCIMENTO', 'Alteração de vencimento'
        VALOR = 'VALOR', 'Alteração de valor'
        ABATIMENTO_DEVOLUCAO = 'ABATIMENTO_DEVOLUCAO', 'Abatimento por devolução'
        USO_CREDITO = 'USO_CREDITO', 'Uso de crédito'

    titulo = models.ForeignKey(
        TituloFinanceiro,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    acao = models.CharField(max_length=24, choices=Acao.choices)
    descricao = models.CharField(max_length=512)
    dados_anteriores = models.JSONField(default=dict, blank=True)
    dados_novos = models.JSONField(default=dict, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']


class CreditoFinanceiroEvento(models.Model):
    class Acao(models.TextChoices):
        CRIACAO = 'CRIACAO', 'Criação'
        EDICAO = 'EDICAO', 'Edição'
        APLICACAO = 'APLICACAO', 'Crédito aplicado'
        CANCELAMENTO = 'CANCELAMENTO', 'Cancelamento'
        REEMBOLSO = 'REEMBOLSO', 'Reembolso'
        ESTORNO_APLICACAO = 'ESTORNO_APLICACAO', 'Estorno de aplicação'

    credito = models.ForeignKey(
        CreditoFinanceiro,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    acao = models.CharField(max_length=24, choices=Acao.choices)
    descricao = models.CharField(max_length=512)
    valor = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    titulo_numero = models.CharField(max_length=40, blank=True)
    baixa_id = models.PositiveIntegerField(null=True, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
