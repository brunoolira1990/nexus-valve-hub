from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


def _default_dias_parcelas():
    return []


def _default_datas():
    return []


class Vendedor(models.Model):
    """Representante comercial; pode estar vinculado a um usuário do sistema."""

    nome = models.CharField(max_length=255)
    codigo = models.CharField(max_length=32, blank=True, db_index=True)
    ativo = models.BooleanField(default=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendedor_comercial',
    )
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=32, blank=True)
    observacoes = models.TextField(blank=True)
    colaborador = models.ForeignKey(
        'cadastros.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendedores',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Vendedor'
        verbose_name_plural = 'Vendedores'

    def __str__(self):
        return self.nome or self.codigo or str(self.pk)


class Proposta(models.Model):
    class HomologacaoFiscalStatus(models.TextChoices):
        NAO_INICIADA = 'NAO_INICIADA', 'Não iniciada'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADA = 'APROVADA', 'Aprovada'
        REPROVADA = 'REPROVADA', 'Reprovada'
        VOLTOU_LEGADO = 'VOLTOU_LEGADO', 'Voltou ao legado'

    numero = models.CharField(max_length=32, unique=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='propostas',
        null=True,
        blank=True,
    )
    cliente_avulso_nome = models.CharField(max_length=255, blank=True)
    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='propostas_emitidas',
        null=True,
        blank=True,
    )
    uf_origem = models.CharField(
        max_length=2,
        blank=True,
        help_text='Denormalizado a partir da UF da empresa emitente (uso em regra fiscal).',
    )
    uf_destino_avulso = models.CharField(
        max_length=2,
        blank=True,
        help_text='UF destino quando o cliente é avulso (sem cadastro com UF).',
    )
    operacao_fiscal = models.CharField(
        max_length=16,
        default='Saída',
        help_text='Fluxo comercial: sempre saída; preenchido automaticamente.',
    )
    usar_cenario_fiscal_saida = models.BooleanField(
        default=False,
        help_text='Quando ativo, tributos de saída usam o cenário fiscal novo (com fallback legado).',
    )
    cenario_fiscal_saida = models.ForeignKey(
        'regras_fiscais.CenarioFiscalSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='propostas',
        help_text='Cenário de saída desta proposta; vazio usa o cenário padrão ativo.',
    )
    data = models.DateField()
    validade = models.DateField()
    vendedor = models.CharField(max_length=255, blank=True)
    vendedor_ref = models.ForeignKey(
        'comercial.Vendedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='propostas',
    )
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_previstos = ArrayField(models.DateField(), default=_default_datas, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    prazo_entrega_texto = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Prazo previsto de entrega (texto livre, ex.: 30 dias após aprovação).',
    )
    validade_dias = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Validade comercial em dias (a partir da data da proposta).',
    )
    frete_texto = models.CharField(
        max_length=255,
        blank=True,
        help_text='Frete / condição de frete comercial (texto livre; não altera NF-e).',
    )
    mensagem_comercial = models.TextField(
        blank=True,
        help_text='Mensagem comercial exibida ao cliente (PDF e proposta).',
    )
    observacoes_proposta = models.TextField(
        blank=True,
        help_text='Observações gerais da proposta comercial.',
    )
    referencia_cliente = models.CharField(
        max_length=128,
        blank=True,
        help_text='Nº da requisição ou cotação do cliente.',
    )
    homologacao_fiscal_status = models.CharField(
        max_length=32,
        choices=HomologacaoFiscalStatus.choices,
        default=HomologacaoFiscalStatus.NAO_INICIADA,
        help_text='Fluxo assistido de homologação do cenário fiscal de saída nesta proposta.',
    )
    homologacao_fiscal_em = models.DateTimeField(null=True, blank=True)
    homologacao_fiscal_observacao = models.TextField(blank=True)
    homologacao_fiscal_resumo = models.JSONField(null=True, blank=True)
    recuperada_em = models.DateTimeField(null=True, blank=True)
    recuperada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='propostas_recuperadas',
    )
    motivo_recuperacao = models.TextField(blank=True)
    status_anterior_recuperacao = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-data', 'numero']


class ItemProposta(models.Model):
    class StatusComercial(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        CONVERTIDO_EM_PEDIDO = 'CONVERTIDO_EM_PEDIDO', 'Convertido em pedido'
        CANCELADO = 'CANCELADO', 'Cancelado'
        PERDIDO = 'PERDIDO', 'Perdido'
        MANTIDO_PARA_DEPOIS = 'MANTIDO_PARA_DEPOIS', 'Mantido para depois'

    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT, null=True, blank=True)
    descricao_avulsa = models.CharField(max_length=255, blank=True)
    ncm_avulso = models.CharField(
        max_length=16,
        blank=True,
        help_text='NCM informado manualmente quando o item não possui produto cadastrado (regra fiscal).',
    )
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    unidade_negociada = models.CharField(max_length=16, blank=True)
    quantidade_negociada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    preco_por_unidade_negociada = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_kg = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_metro = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    custo_utilizado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    despesas = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    ipi_entrada_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    ipi_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    st_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    outros_impostos_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    custo_final = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    icms_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    pis_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    cofins_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    ipi_saida_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    regra_fiscal_id = models.PositiveIntegerField(null=True, blank=True)
    irpj_estimado_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    csll_estimada_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    comissao_percentual = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    frete_saida = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    outras_despesas_saida = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    modo_preco = models.CharField(max_length=16, default='sugerido')
    preco_sugerido = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    preco_final = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    margem_resultante = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    lucro_resultante = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    snapshot_produto = models.JSONField(default=dict, blank=True)
    status_comercial = models.CharField(
        max_length=32,
        choices=StatusComercial.choices,
        default=StatusComercial.PENDENTE,
        db_index=True,
    )
    pedido_venda_gerado = models.ForeignKey(
        'PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_proposta_convertidos',
    )
    item_pedido_venda_gerado = models.ForeignKey(
        'ItemPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='item_proposta_origem',
    )
    convertido_em = models.DateTimeField(null=True, blank=True)
    convertido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_proposta_convertidos',
    )
    cancelado_em = models.DateTimeField(null=True, blank=True)
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_proposta_cancelados',
    )
    motivo_cancelamento_item = models.TextField(blank=True)


class HomologacaoFiscalPropostaEvento(models.Model):
    """Fase Saída 3.10 — trilha de auditoria da homologação fiscal por proposta."""

    class TipoEvento(models.TextChoices):
        INICIADA = 'INICIADA', 'Homologação iniciada'
        RECALCULADA = 'RECALCULADA', 'Homologação recalculada'
        APROVADA = 'APROVADA', 'Homologação aprovada'
        REPROVADA = 'REPROVADA', 'Homologação reprovada'
        VOLTOU_LEGADO = 'VOLTOU_LEGADO', 'Voltou para regra legada'
        ALTEROU_CENARIO = 'ALTEROU_CENARIO', 'Cenário fiscal alterado'

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.CASCADE,
        related_name='homologacao_fiscal_eventos',
    )
    tipo_evento = models.CharField(max_length=32, choices=TipoEvento.choices)
    status_resultante = models.CharField(max_length=32)
    usar_cenario_fiscal_saida = models.BooleanField(default=False)
    cenario_fiscal_saida = models.ForeignKey(
        'regras_fiscais.CenarioFiscalSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homologacao_fiscal_eventos',
    )
    cenario_fiscal_saida_nome = models.CharField(max_length=255, blank=True)
    resumo = models.JSONField(null=True, blank=True)
    itens = models.JSONField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homologacao_fiscal_proposta_eventos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['proposta', '-criado_em']),
        ]


class PropostaComercialHistorico(models.Model):
    """Trilha de auditoria comercial da proposta (conversão parcial, recuperação, itens)."""

    class TipoEvento(models.TextChoices):
        PROPOSTA_RECUPERADA = 'PROPOSTA_RECUPERADA', 'Proposta recuperada'
        PEDIDO_GERADO = 'PEDIDO_GERADO', 'Pedido de venda gerado'
        ITEM_CONVERTIDO = 'ITEM_CONVERTIDO', 'Item convertido em pedido'
        ITEM_CANCELADO = 'ITEM_CANCELADO', 'Item cancelado'
        ITEM_MANTIDO_PENDENTE = 'ITEM_MANTIDO_PENDENTE', 'Item mantido pendente'
        PEDIDO_EXCLUIDO_STATUS_REVERTIDO = (
            'PEDIDO_EXCLUIDO_STATUS_REVERTIDO',
            'Pedido excluído — status revertido',
        )
        REPARO_STATUS_COMERCIAL_PEDIDO = (
            'REPARO_STATUS_COMERCIAL_PEDIDO',
            'Reparo de status comercial (pedido excluído)',
        )

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.CASCADE,
        related_name='historico_comercial',
    )
    tipo_evento = models.CharField(max_length=32, choices=TipoEvento.choices)
    descricao = models.TextField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_comerciais_proposta',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    dados_json = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['proposta', '-criado_em']),
        ]
        verbose_name = 'Histórico comercial da proposta'
        verbose_name_plural = 'Históricos comerciais das propostas'


class PedidoVenda(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='pedidos_venda_emitidos',
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='pedidos_venda',
    )
    data = models.DateField()
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_previstos = ArrayField(models.DateField(), default=_default_datas, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    vendedor = models.CharField(max_length=255, blank=True)
    vendedor_ref = models.ForeignKey(
        'comercial.Vendedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_venda',
    )
    prazo_entrega = models.DateField(
        null=True,
        blank=True,
        help_text='Data prevista de entrega (legado/opcional); preferir prazo_entrega_texto.',
    )
    prazo_entrega_texto = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Prazo previsto de entrega herdado da proposta ou informado no pedido.',
    )
    observacoes_comerciais = models.TextField(blank=True)
    observacoes_internas = models.TextField(blank=True)
    snapshot_conversao = models.JSONField(null=True, blank=True, help_text='Snapshot comercial/fiscal no momento da conversão.')
    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_gerados',
    )

    class Meta:
        ordering = ['-data', 'numero']


class ItemPedidoVenda(models.Model):
    class StatusItem(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PARCIAL = 'PARCIAL', 'Parcialmente faturado'
        FATURADO = 'FATURADO', 'Faturado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    pedido = models.ForeignKey(PedidoVenda, on_delete=models.CASCADE, related_name='itens')
    item_proposta = models.ForeignKey(
        ItemProposta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_pedido_venda',
    )
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    unidade_negociada = models.CharField(max_length=16, blank=True)
    quantidade_negociada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    preco_por_unidade_negociada = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_kg = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_metro = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    snapshot_fiscal = models.JSONField(null=True, blank=True, help_text='Impostos/origem fiscal herdados da proposta na conversão.')
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    snapshot_produto = models.JSONField(default=dict, blank=True)
    quantidade_faturada = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0'),
        help_text='Quantidade já confirmada em faturamentos (não inclui rascunhos).',
    )
    status_item = models.CharField(
        max_length=16,
        choices=StatusItem.choices,
        default=StatusItem.PENDENTE,
    )

    class Meta:
        ordering = ['id']


class FaturamentoPedidoVenda(models.Model):
    """Solicitação de faturamento parcial/total — preparação para NF-e (sem emissão nesta fase)."""

    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        PRONTO_PARA_NFE = 'PRONTO_PARA_NFE', 'Pronto para NF-e'
        GERADO_NFE = 'GERADO_NFE', 'NF-e gerada'
        CANCELADO = 'CANCELADO', 'Cancelado'

    pedido = models.ForeignKey(
        PedidoVenda,
        on_delete=models.CASCADE,
        related_name='faturamentos',
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    numero_faturamento = models.CharField(max_length=32, blank=True, db_index=True)
    cliente_snapshot = models.JSONField(default=dict, blank=True)
    observacao = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faturamentos_pedido_venda_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    nfe_saida = models.ForeignKey(
        'fiscal.NFeSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faturamento_vinculado',
    )
    nfe_saida_gerada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']


class ItemFaturamentoPedidoVenda(models.Model):
    faturamento = models.ForeignKey(
        FaturamentoPedidoVenda,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    item_pedido = models.ForeignKey(
        ItemPedidoVenda,
        on_delete=models.PROTECT,
        related_name='itens_faturamento',
    )
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    desconto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    snapshot_fiscal = models.JSONField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ['id']


class SequenciaComercial(models.Model):
    """Sequência diária para proposta e pedido de venda (PROP/PV-AAAAMMDD-NNNN)."""

    class Tipo(models.TextChoices):
        PROPOSTA = 'PROPOSTA', 'Proposta'
        PEDIDO_VENDA = 'PEDIDO_VENDA', 'Pedido de venda'
        FATURAMENTO = 'FATURAMENTO', 'Faturamento'

    tipo = models.CharField(max_length=32, choices=Tipo.choices, db_index=True)
    data_referencia = models.DateField(db_index=True)
    proximo_numero = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Sequência comercial'
        verbose_name_plural = 'Sequências comerciais'
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'data_referencia'],
                name='comercial_sequenciacomercial_tipo_data_uniq',
            ),
        ]
        ordering = ['-data_referencia', 'tipo']

    def __str__(self):
        return f'{self.tipo} {self.data_referencia} → próximo {self.proximo_numero}'


class SequenciaPedidoCompra(models.Model):
    """Controle de sequência diária para numeração PC-AAAAMMDD-NNNN."""

    data_referencia = models.DateField(unique=True, db_index=True)
    proximo_numero = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-data_referencia']
        verbose_name = 'Sequência pedido de compra'
        verbose_name_plural = 'Sequências pedidos de compra'

    def __str__(self):
        return f'{self.data_referencia} → próximo {self.proximo_numero}'


class PedidoCompra(models.Model):
    numero = models.CharField(max_length=32, unique=True)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        related_name='pedidos_compra',
    )
    data = models.DateField()
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_previstos = ArrayField(models.DateField(), default=_default_datas, blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    prazo_entrega_texto = models.CharField(max_length=255, blank=True)
    data_prevista_entrega = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['-data', 'numero']


class ItemPedidoCompra(models.Model):
    pedido = models.ForeignKey(PedidoCompra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    quantidade_recebida = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    valor_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    unidade_negociada = models.CharField(max_length=16, blank=True)
    quantidade_negociada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    preco_por_unidade_negociada = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_kg = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    preco_por_metro = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))
    snapshot_produto = models.JSONField(default=dict, blank=True)
    ipi_percentual = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'))
    ipi_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    icms_st_percentual = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'))
    icms_st_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    desconto_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    frete_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    outras_despesas_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_produtos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_total_item = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))


class AnaliseFinanceiraProposta(models.Model):
    """Liberação financeira manual vinculada à Proposta Comercial (MVP)."""

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        APROVADA = 'APROVADA', 'Aprovada'
        APROVADA_COM_AJUSTE = 'APROVADA_COM_AJUSTE', 'Aprovada com ajuste'
        DEVOLVIDA_PARA_AJUSTE = 'DEVOLVIDA_PARA_AJUSTE', 'Devolvida para ajuste'
        NAO_APROVADA = 'NAO_APROVADA', 'Não aprovada'
        EXPIRADA = 'EXPIRADA', 'Expirada'
        SUBSTITUIDA = 'SUBSTITUIDA', 'Substituída'

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.CASCADE,
        related_name='analises_financeiras',
    )
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='analises_financeiras_proposta',
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    versao = models.PositiveIntegerField(default=1)
    solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analises_financeiras_solicitadas',
    )
    solicitada_em = models.DateTimeField(auto_now_add=True)
    iniciada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analises_financeiras_iniciadas',
    )
    iniciada_em = models.DateTimeField(null=True, blank=True)
    decidida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analises_financeiras_decididas',
    )
    decidida_em = models.DateTimeField(null=True, blank=True)
    observacao_vendedor = models.TextField(blank=True)
    justificativa_decisao = models.TextField(blank=True)
    valor_solicitado = models.DecimalField(max_digits=14, decimal_places=2)
    valor_maximo_aprovado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    valida_ate = models.DateField(null=True, blank=True)
    snapshot_proposta = models.JSONField(default=dict, blank=True)
    snapshot_indicadores = models.JSONField(default=dict, blank=True)
    condicao_solicitada = models.JSONField(default=dict, blank=True)
    condicao_aprovada = models.JSONField(default=dict, blank=True)
    substituida_por = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='substitui',
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-solicitada_em', '-id']
        verbose_name = 'Análise financeira de proposta'
        verbose_name_plural = 'Análises financeiras de propostas'
        permissions = (
            ('solicitar_analisefinanceiraproposta', 'Pode solicitar análise financeira de proposta'),
            ('decidir_analisefinanceiraproposta', 'Pode decidir análise financeira de proposta'),
            ('ver_detalhe_financeiro_analisefinanceiraproposta', 'Pode ver detalhe financeiro da análise'),
        )
        constraints = [
            models.UniqueConstraint(
                fields=['proposta'],
                condition=models.Q(status__in=['PENDENTE', 'EM_ANALISE']),
                name='uniq_analise_fin_ativa_por_proposta',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'solicitada_em'], name='analise_fin_status_sol_idx'),
            models.Index(fields=['cliente', 'status'], name='analise_fin_cli_status_idx'),
        ]

    def __str__(self) -> str:
        return f'Análise #{self.pk} proposta={self.proposta_id} {self.status}'


class AnaliseFinanceiraPropostaEvento(models.Model):
    """Histórico append-only das análises financeiras de proposta."""

    class Tipo(models.TextChoices):
        SOLICITADA = 'SOLICITADA', 'Solicitada'
        INICIADA = 'INICIADA', 'Iniciada'
        APROVADA = 'APROVADA', 'Aprovada'
        APROVADA_COM_AJUSTE = 'APROVADA_COM_AJUSTE', 'Aprovada com ajuste'
        DEVOLVIDA = 'DEVOLVIDA', 'Devolvida'
        NAO_APROVADA = 'NAO_APROVADA', 'Não aprovada'
        EXPIRADA = 'EXPIRADA', 'Expirada'
        SUBSTITUIDA = 'SUBSTITUIDA', 'Substituída'

    analise = models.ForeignKey(
        AnaliseFinanceiraProposta,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    tipo = models.CharField(max_length=32, choices=Tipo.choices)
    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_analise_financeira_proposta',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    dados = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        default_permissions = ('view',)
        verbose_name = 'Evento de análise financeira'
        verbose_name_plural = 'Eventos de análise financeira'
