"""Expedição / Logística — controle operacional manual (Fase 1A). Sem estoque/financeiro/fiscal."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class TipoOperacaoExpedicao(models.TextChoices):
    ESTOQUE_PROPRIO = 'ESTOQUE_PROPRIO', 'Estoque próprio'
    RETIRADA_FORNECEDOR = 'RETIRADA_FORNECEDOR', 'Retirada fornecedor'
    ENTREGA_DIRETA_FORNECEDOR_CLIENTE = (
        'ENTREGA_DIRETA_FORNECEDOR_CLIENTE',
        'Entrega direta fornecedor → cliente',
    )
    RETIRADA_FORNECEDOR_TRANSPORTADORA = (
        'RETIRADA_FORNECEDOR_TRANSPORTADORA',
        'Retirada fornecedor → transportadora',
    )
    MISTO = 'MISTO', 'Misto'
    OUTROS = 'OUTROS', 'Outros'


class StatusExpedicao(models.TextChoices):
    RASCUNHO = 'RASCUNHO', 'Rascunho'
    AGUARDANDO_SEPARACAO = 'AGUARDANDO_SEPARACAO', 'Aguardando separação'
    AGUARDANDO_RETIRADA_FORNECEDOR = 'AGUARDANDO_RETIRADA_FORNECEDOR', 'Aguardando retirada fornecedor'
    MOTORISTA_ENVIADO = 'MOTORISTA_ENVIADO', 'Motorista enviado'
    RETIRADO_FORNECEDOR = 'RETIRADO_FORNECEDOR', 'Retirado fornecedor'
    EM_TRANSITO = 'EM_TRANSITO', 'Em trânsito'
    ENTREGUE_TRANSPORTADORA = 'ENTREGUE_TRANSPORTADORA', 'Entregue transportadora'
    ENTREGUE_CLIENTE = 'ENTREGUE_CLIENTE', 'Entregue cliente'
    OCORRENCIA = 'OCORRENCIA', 'Ocorrência'
    CANCELADO = 'CANCELADO', 'Cancelado'


class Expedicao(models.Model):
    """Registro operacional de expedição — referências manuais, sem efeitos colaterais."""

    codigo = models.CharField(max_length=32, unique=True, db_index=True)
    tipo_operacao = models.CharField(max_length=48, choices=TipoOperacaoExpedicao.choices)
    status = models.CharField(
        max_length=40,
        choices=StatusExpedicao.choices,
        default=StatusExpedicao.RASCUNHO,
        db_index=True,
    )

    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )

    motorista_nome = models.CharField(max_length=120, blank=True)
    motorista_documento = models.CharField(max_length=32, blank=True)
    telefone_motorista = models.CharField(max_length=32, blank=True)
    placa_veiculo = models.CharField(max_length=16, blank=True)

    volumes = models.PositiveIntegerField(default=0)
    peso_bruto = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    peso_liquido = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)

    data_prevista_retirada = models.DateField(null=True, blank=True)
    data_prevista_entrega = models.DateField(null=True, blank=True)
    data_hora_retirada_real = models.DateTimeField(null=True, blank=True)
    data_hora_entrega_real = models.DateTimeField(null=True, blank=True)

    observacoes = models.TextField(blank=True)
    ocorrencia_descricao = models.TextField(blank=True)

    pedido_venda = models.ForeignKey(
        'comercial.PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    faturamento = models.ForeignKey(
        'comercial.FaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    nfe_saida = models.ForeignKey(
        'fiscal.NFeSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    alocacao_atendimento = models.ForeignKey(
        'fiscal.AlocacaoAtendimento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    nfe_entrada = models.ForeignKey(
        'fiscal.NFeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )
    cte_entrada = models.ForeignKey(
        'fiscal.CTeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes',
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes_criadas',
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expedicoes_atualizadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Expedição'
        verbose_name_plural = 'Expedições'
        indexes = [
            models.Index(fields=['status', '-criado_em']),
            models.Index(fields=['tipo_operacao', '-criado_em']),
            models.Index(fields=['data_prevista_entrega']),
            models.Index(fields=['data_prevista_retirada']),
        ]

    def __str__(self) -> str:
        return self.codigo or f'Expedição #{self.pk}'
