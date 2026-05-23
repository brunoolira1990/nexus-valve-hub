from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class EstoqueCorrida(models.Model):
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE, related_name='estoques_corrida')
    corrida = models.ForeignKey('corridas.Corrida', on_delete=models.CASCADE, related_name='estoques')
    saldo = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))

    class Meta:
        unique_together = [['produto', 'corrida']]
        ordering = ['produto_id', 'corrida_id']


class NFeEntrada(models.Model):
    numero = models.CharField(max_length=64)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.PROTECT,
        related_name='nf_entradas',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas',
    )
    cte = models.ForeignKey(
        'fiscal.CTeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entradas_vinculadas',
    )

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF entrada'


class ItemNFeEntrada(models.Model):
    nf = models.ForeignKey(NFeEntrada, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    snapshot_produto = models.JSONField(default=dict, blank=True)


class NFeSaida(models.Model):
    class ModoAtendimentoEstoque(models.TextChoices):
        IMEDIATO = 'IMEDIATO', 'Baixa física na emissão'
        ANTECIPADO = 'ANTECIPADO', 'Compromisso sem baixa física'

    numero = models.CharField(max_length=64)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='nf_saidas',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    modo_atendimento_estoque = models.CharField(
        max_length=16,
        choices=ModoAtendimentoEstoque.choices,
        default=ModoAtendimentoEstoque.IMEDIATO,
    )
    status = models.CharField(max_length=64, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=list, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    vencimentos_finais = ArrayField(models.DateField(), default=list, blank=True)
    titulos_receber = models.JSONField(default=list, blank=True)
    pedido_venda = models.ForeignKey(
        'comercial.PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas',
    )
    faturamento_pedido_venda = models.ForeignKey(
        'comercial.FaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_geradas',
    )
    observacao_origem = models.TextField(
        blank=True,
        help_text='Observação da geração a partir do faturamento (rascunho).',
    )
    motivo_cancelamento = models.TextField(
        blank=True,
        help_text='Motivo do cancelamento interno (simulação pré-SEFAZ).',
    )
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_canceladas',
    )
    efeitos_autorizacao_aplicados_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando os efeitos operacionais de autorização (interna) foram aplicados.',
    )
    efeitos_cancelamento_aplicados_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando os efeitos operacionais de cancelamento (interno) foram aplicados.',
    )
    efeitos_cancelamento_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_cancelamento_efeitos',
    )
    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas',
    )
    modalidade_frete = models.CharField(
        max_length=1,
        blank=True,
        default='9',
        help_text='Modalidade do frete (9=sem frete, 0=CIF, 1=FOB, etc.).',
    )
    valor_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    quantidade_volumes = models.PositiveIntegerField(default=0)
    peso_bruto = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_liquido = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    observacoes_nfe = models.TextField(
        blank=True,
        help_text='Observações complementares da NF-e (editáveis em rascunho).',
    )
    informacoes_adicionais = models.TextField(
        blank=True,
        help_text='Informações adicionais de interesse do fisco/contribuinte.',
    )
    pedido_cliente_numero = models.CharField(max_length=64, blank=True)
    pedido_cliente_observacao = models.TextField(blank=True)
    informacoes_fisco = models.TextField(
        blank=True,
        help_text='Informações ao Fisco (prévia/preparatório).',
    )
    observacoes_internas = models.TextField(
        blank=True,
        help_text='Observações internas ERP — não saem no XML/DANFE.',
    )
    especie_volumes = models.CharField(max_length=64, blank=True)
    marca_volumes = models.CharField(max_length=64, blank=True)
    numeracao_volumes = models.CharField(max_length=64, blank=True)
    placa_veiculo = models.CharField(max_length=16, blank=True)
    uf_veiculo = models.CharField(max_length=2, blank=True)

    class StatusConferencia(models.TextChoices):
        EM_CONFERENCIA = 'EM_CONFERENCIA', 'Em conferência'
        COM_PENDENCIAS = 'COM_PENDENCIAS', 'Com pendências'
        CONFERIDA = 'CONFERIDA', 'Conferida'
        PRONTA_PARA_EMISSAO = 'PRONTA_PARA_EMISSAO', 'Pronta para emissão'

    status_conferencia = models.CharField(
        max_length=24,
        choices=StatusConferencia.choices,
        default=StatusConferencia.EM_CONFERENCIA,
    )
    conferencia_validada_em = models.DateTimeField(null=True, blank=True)
    conferencia_validada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_conferencia_validadas',
    )
    conferencia_marcada_pronta_em = models.DateTimeField(null=True, blank=True)
    conferencia_marcada_pronta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saidas_conferencia_prontas',
    )
    conferencia_ultima_mensagem = models.TextField(blank=True)

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF saída'


class NFeSaidaEvento(models.Model):
    """Trilha operacional da NF-e Saída (rascunho, efeitos internos — sem SEFAZ)."""

    class TipoEvento(models.TextChoices):
        RASCUNHO_CRIADO = 'RASCUNHO_CRIADO', 'Rascunho criado'
        VALIDADA = 'VALIDADA', 'Validada (pré-emissão)'
        AUTORIZACAO_EFEITOS_APLICADOS = 'AUTORIZACAO_EFEITOS_APLICADOS', 'Efeitos de autorização aplicados (interno)'
        CANCELAMENTO_EFEITOS_APLICADOS = 'CANCELAMENTO_EFEITOS_APLICADOS', 'Efeitos de cancelamento aplicados (interno)'
        CANCELADA = 'CANCELADA', 'Cancelada (interno)'
        ESTORNO_FATURAMENTO = 'ESTORNO_FATURAMENTO', 'Estorno de faturamento vinculado'
        IMPOSTOS_ATUALIZADOS = 'IMPOSTOS_ATUALIZADOS', 'Impostos atualizados da regra atual'
        CONFERENCIA_SALVA = 'CONFERENCIA_SALVA', 'Conferência salva'
        CONFERENCIA_VALIDADA = 'CONFERENCIA_VALIDADA', 'Conferência validada'
        CONFERENCIA_COM_PENDENCIAS = 'CONFERENCIA_COM_PENDENCIAS', 'Conferência com pendências'
        PRONTA_PARA_EMISSAO = 'PRONTA_PARA_EMISSAO', 'Pronta para emissão'
        PRONTIDAO_INVALIDADA = 'PRONTIDAO_INVALIDADA', 'Prontidão invalidada'
        OBSERVACAO = 'OBSERVACAO', 'Observação'

    nfe_saida = models.ForeignKey(
        NFeSaida,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    tipo_evento = models.CharField(max_length=40, choices=TipoEvento.choices)
    pedido_venda = models.ForeignKey(
        'comercial.PedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_nfe_saida',
    )
    faturamento_pedido_venda = models.ForeignKey(
        'comercial.FaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_nfe_saida',
    )
    status_anterior = models.CharField(max_length=64, blank=True)
    status_novo = models.CharField(max_length=64, blank=True)
    resumo = models.JSONField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_nfe_saida_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['nfe_saida', '-criado_em']),
        ]


class ItemNFeSaida(models.Model):
    nf = models.ForeignKey(NFeSaida, on_delete=models.CASCADE, related_name='itens')
    item_faturamento_pedido = models.ForeignKey(
        'comercial.ItemFaturamentoPedidoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_nfe_saida',
    )
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    corrida = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    snapshot_produto = models.JSONField(default=dict, blank=True)
    snapshot_fiscal = models.JSONField(null=True, blank=True)
    snapshot_comercial = models.JSONField(null=True, blank=True)
    pedido_cliente_numero = models.CharField(max_length=64, blank=True)
    pedido_cliente_item = models.CharField(max_length=64, blank=True)
    observacao_item = models.TextField(blank=True)
    informacao_adicional_item = models.TextField(blank=True)


class AtendimentoEstoque(models.Model):
    class OrigemTipo(models.TextChoices):
        NF_SAIDA = 'NF_SAIDA', 'NF de saída'

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PARCIAL = 'PARCIAL', 'Parcial'
        ATENDIDO = 'ATENDIDO', 'Atendido'
        CANCELADO = 'CANCELADO', 'Cancelado'

    origem_tipo = models.CharField(
        max_length=16,
        choices=OrigemTipo.choices,
        default=OrigemTipo.NF_SAIDA,
    )
    item_nf_saida = models.ForeignKey(
        ItemNFeSaida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_estoque',
    )
    nf_saida = models.ForeignKey(
        NFeSaida,
        on_delete=models.CASCADE,
        related_name='atendimentos_estoque',
    )
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.PROTECT,
        related_name='atendimentos_estoque',
    )
    quantidade_comprometida = models.DecimalField(max_digits=14, decimal_places=3)
    quantidade_atendida = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    unidade = models.CharField(max_length=16, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    estoque_fisico_aplicado = models.BooleanField(default=False)
    estoque_aplicado_em = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    motivo_cancelamento = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    atendido_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        indexes = [
            models.Index(fields=['produto', 'status']),
            models.Index(fields=['nf_saida', 'status']),
            models.Index(fields=['criado_em']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantidade_comprometida__gt=0),
                name='ck_atend_estoque_qtd_comprometida_pos',
            ),
            models.CheckConstraint(
                check=models.Q(quantidade_atendida__gte=0),
                name='ck_atend_estoque_qtd_atendida_nonneg',
            ),
            models.CheckConstraint(
                check=models.Q(status='CANCELADO')
                | models.Q(quantidade_atendida__lte=models.F('quantidade_comprometida')),
                name='ck_atend_estoque_qtd_atend_lte_comp',
            ),
            models.UniqueConstraint(
                fields=['item_nf_saida'],
                condition=models.Q(~models.Q(status='CANCELADO'), item_nf_saida__isnull=False),
                name='uniq_atend_estoque_item_nf_saida_ativo',
            ),
        ]

    def __str__(self) -> str:
        return f'Atendimento #{self.pk} NF {self.nf_saida_id} item {self.item_nf_saida_id}'


class AtendimentoEstoqueLinha(models.Model):
    atendimento = models.ForeignKey(
        AtendimentoEstoque,
        on_delete=models.CASCADE,
        related_name='linhas',
    )
    item_conferencia = models.ForeignKey(
        'ItemNFeEntradaConferencia',
        on_delete=models.PROTECT,
        related_name='linhas_atendimento_estoque',
    )
    conferencia = models.ForeignKey(
        'NFeEntradaConferencia',
        on_delete=models.PROTECT,
        related_name='linhas_atendimento_estoque',
    )
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    item_certificado_fornecedor = models.ForeignKey(
        'qualidade.ItemCertificadoFornecedorEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linhas_atendimento_estoque',
    )
    corrida_texto = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em', 'id']
        indexes = [
            models.Index(fields=['atendimento']),
            models.Index(fields=['item_conferencia']),
            models.Index(fields=['conferencia']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantidade__gt=0),
                name='ck_atend_estoque_linha_qtd_pos',
            ),
        ]

    def __str__(self) -> str:
        return f'Linha atend. #{self.pk} conf {self.item_conferencia_id} → atend {self.atendimento_id}'


class NFeSaidaHistoricaImportada(models.Model):
    """NF-e de saída emitida fora do ERP, importada por XML para base fiscal/gerencial."""

    chave_acesso = models.CharField(max_length=44, unique=True, db_index=True)
    numero = models.CharField(max_length=16)
    serie = models.CharField(max_length=4, blank=True)
    modelo = models.CharField(max_length=4, blank=True)
    dh_emissao = models.DateTimeField()
    tp_amb = models.CharField(max_length=1, blank=True)
    tp_nf = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=120, blank=True)
    versao_layout = models.CharField(max_length=16, blank=True)

    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    protocolo = models.CharField(max_length=30, blank=True)

    valor_produtos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_total_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_seg = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_desc = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_outro = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    emit_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    totais_json = models.JSONField(default=dict, blank=True)
    reforma_e_outros_json = models.JSONField(default=dict, blank=True)
    prot_json = models.JSONField(default=dict, blank=True)
    cancelada = models.BooleanField(default=False)
    status_documento = models.CharField(max_length=32, default='autorizada')
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    tipo_evento = models.CharField(max_length=16, blank=True)
    evento_cancelamento_json = models.JSONField(default=dict, blank=True)
    evento_cancelamento_id = models.CharField(max_length=80, blank=True)

    empresa_emitente = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saida_historicas_importadas',
    )
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_saida_historicas_importadas',
    )
    papel_empresa_no_documento = models.CharField(max_length=32, blank=True)

    importada = models.BooleanField(default=True)
    origem_externa = models.BooleanField(default=True)
    historica = models.BooleanField(default=True)

    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        verbose_name = 'NF-e saída importada (histórico)'
        verbose_name_plural = 'NF-e saída importadas (histórico)'

    def __str__(self):
        return f'{self.chave_acesso} — {self.numero}/{self.serie}'


class NFeEntradaHistoricaImportada(models.Model):
    """NF-e de entrada emitida fora do ERP, importada por XML para base fiscal/gerencial."""

    chave_acesso = models.CharField(max_length=44, unique=True, db_index=True)
    numero = models.CharField(max_length=16)
    serie = models.CharField(max_length=4, blank=True)
    modelo = models.CharField(max_length=4, blank=True)
    dh_emissao = models.DateTimeField()
    tp_amb = models.CharField(max_length=1, blank=True)
    tp_nf = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=120, blank=True)
    versao_layout = models.CharField(max_length=16, blank=True)

    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    protocolo = models.CharField(max_length=30, blank=True)

    valor_produtos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_total_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_seg = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_desc = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    v_outro = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    emit_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    totais_json = models.JSONField(default=dict, blank=True)
    reforma_e_outros_json = models.JSONField(default=dict, blank=True)
    prot_json = models.JSONField(default=dict, blank=True)

    empresa_destinataria = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entrada_historicas_importadas_como_destinataria',
    )
    fornecedor_emitente = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nf_entrada_historicas_importadas_como_emitente',
    )
    papel_empresa_no_documento = models.CharField(max_length=32, blank=True)

    importada = models.BooleanField(default=True)
    origem_externa = models.BooleanField(default=True)
    historica = models.BooleanField(default=True)

    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        verbose_name = 'NF-e entrada importada (histórico)'
        verbose_name_plural = 'NF-e entrada importadas (histórico)'

    def __str__(self):
        return f'{self.chave_acesso} — {self.numero}/{self.serie}'


class ItemNFeEntradaHistoricaImportada(models.Model):
    nf = models.ForeignKey(
        NFeEntradaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    n_item = models.PositiveIntegerField()
    prod_json = models.JSONField(default=dict, blank=True)
    imposto_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['nf_id', 'n_item']

    def __str__(self):
        return f'Item {self.n_item} NF entrada hist. {self.nf_id}'


class NFeEntradaConferencia(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        CONFERIDA = 'CONFERIDA', 'Conferida'
        PREPARADA = 'PREPARADA', 'Entrada preparada'
        CANCELADA = 'CANCELADA', 'Cancelada/Revertida'

    nf_entrada_historica = models.OneToOneField(
        NFeEntradaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='conferencia',
    )
    pedido_compra = models.ForeignKey(
        'comercial.PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conferencias_nf_entrada',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDENTE)
    divergencias_aceitas = models.BooleanField(default=False)
    observacao_divergencias = models.TextField(blank=True)
    preparado_em = models.DateTimeField(null=True, blank=True)
    estoque_aplicado_em = models.DateTimeField(null=True, blank=True)
    estoque_aplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conferencias_estoque_aplicado',
    )
    estoque_aplicado_observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']


class ItemNFeEntradaConferencia(models.Model):
    class Status(models.TextChoices):
        PENDENTE_PRODUTO = 'PENDENTE_PRODUTO', 'Pendente produto'
        PRODUTO_VINCULADO = 'PRODUTO_VINCULADO', 'Produto vinculado'
        CONFERIDO = 'CONFERIDO', 'Conferido'
        DIVERGENTE = 'DIVERGENTE', 'Divergente'
        IGNORADO = 'IGNORADO', 'Ignorado'

    conferencia = models.ForeignKey(
        NFeEntradaConferencia,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    item_nfe_historico = models.OneToOneField(
        ItemNFeEntradaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='item_conferencia',
    )
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_conferencia_nfe_entrada',
    )
    item_pedido_compra = models.ForeignKey(
        'comercial.ItemPedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_conferencia_nfe_entrada',
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDENTE_PRODUTO)
    motivo_ignorado = models.CharField(max_length=255, blank=True)
    observacao = models.TextField(blank=True)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    rastreabilidade_observacao = models.CharField(max_length=255, blank=True)
    unidade_nf = models.CharField(max_length=16, blank=True)
    quantidade_nf = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    valor_unitario_nf = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    valor_total_nf = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    unidade_estoque_calculada = models.CharField(max_length=16, blank=True)
    quantidade_estoque_calculada = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    peso_total_kg = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    metros_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    barras_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    toneladas_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    divergencias = models.JSONField(default=list, blank=True)
    alertas = models.JSONField(default=list, blank=True)
    snapshot_produto = models.JSONField(default=dict, blank=True)
    snapshot_pedido = models.JSONField(default=dict, blank=True)
    estoque_aplicado_em = models.DateTimeField(null=True, blank=True)
    quantidade_estoque_aplicada = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0'),
    )
    corrida_estoque = models.ForeignKey(
        'corridas.Corrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='itens_conferencia_entrada',
    )
    estoque_corrida = models.ForeignKey(
        'EstoqueCorrida',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='itens_conferencia_entrada',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_nfe_historico__n_item']


class ItemNFeSaidaHistoricaImportada(models.Model):
    nf = models.ForeignKey(
        NFeSaidaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    n_item = models.PositiveIntegerField()
    prod_json = models.JSONField(default=dict, blank=True)
    imposto_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['nf_id', 'n_item']

    def __str__(self):
        return f'Item {self.n_item} NF hist. {self.nf_id}'


class EventoNFeSaidaHistoricaPendente(models.Model):
    """Evento de NF-e (XML) recebido antes da nota correspondente existir na base — conciliação posterior."""

    class Direcao(models.TextChoices):
        SAIDA = 'SAIDA', 'Saída'
        ENTRADA = 'ENTRADA', 'Entrada'

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        APLICADO = 'APLICADO', 'Aplicado'
        IGNORADO = 'IGNORADO', 'Ignorado'

    chave_nfe = models.CharField(max_length=44, db_index=True)
    tipo_evento = models.CharField(max_length=16, db_index=True)
    descricao_evento = models.CharField(max_length=255, blank=True)
    sequencia_evento = models.PositiveSmallIntegerField(default=0)
    data_evento = models.DateTimeField(null=True, blank=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    id_evento = models.CharField(max_length=80, blank=True)
    justificativa = models.TextField(blank=True)
    evento_json = models.JSONField(default=dict, blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    direcao = models.CharField(max_length=8, choices=Direcao.choices, default=Direcao.SAIDA)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    mensagem = models.TextField(blank=True)
    nf = models.ForeignKey(
        NFeSaidaHistoricaImportada,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='eventos_pendentes_resolvidos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['chave_nfe', 'tipo_evento', 'protocolo_evento', 'id_evento'],
                name='uniq_evento_hist_pendente_dedup',
            )
        ]

    def __str__(self) -> str:
        return f'Evento pendente {self.tipo_evento} chave {self.chave_nfe[:8]}…'


class EventoNFeSaidaHistoricaImportada(models.Model):
    nf = models.ForeignKey(
        NFeSaidaHistoricaImportada,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    chave_acesso = models.CharField(max_length=44, db_index=True)
    tipo_evento = models.CharField(max_length=16, db_index=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    id_evento = models.CharField(max_length=80, blank=True)
    sequencial_evento = models.PositiveSmallIntegerField(default=0)
    data_evento = models.DateTimeField(null=True, blank=True)
    evento_json = models.JSONField(default=dict, blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-importado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['nf', 'tipo_evento', 'protocolo_evento', 'id_evento'],
                name='uniq_nf_hist_evento_dedup',
            )
        ]


class CTeEntrada(models.Model):
    numero = models.CharField(max_length=64, unique=True)
    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.PROTECT,
        related_name='ctes',
    )
    tomador = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.PROTECT,
        related_name='ctes_como_tomador',
    )
    valor_frete = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    data = models.DateField()
    nfe_ids = ArrayField(models.IntegerField(), default=list, blank=True)

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'CT-e entrada'


class CTeHistoricoImportado(models.Model):
    """CT-e emitido fora do ERP, importado por XML para base fiscal/logística/gerencial."""

    chave_acesso = models.CharField(max_length=44, unique=True, db_index=True)
    numero = models.CharField(max_length=16)
    serie = models.CharField(max_length=4, blank=True)
    modelo = models.CharField(max_length=4, blank=True)
    dh_emissao = models.DateTimeField()
    tp_amb = models.CharField(max_length=1, blank=True)
    nat_op = models.CharField(max_length=120, blank=True)
    cfop = models.CharField(max_length=8, blank=True)
    versao_layout = models.CharField(max_length=16, blank=True)

    cstat = models.CharField(max_length=8, blank=True)
    xmotivo = models.CharField(max_length=255, blank=True)
    protocolo = models.CharField(max_length=30, blank=True)

    cancelado = models.BooleanField(default=False)
    status_documento = models.CharField(max_length=32, default='autorizado')
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    protocolo_cancelamento = models.CharField(max_length=30, blank=True)
    motivo_cancelamento = models.CharField(max_length=255, blank=True)

    valor_total_servico = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    valor_receber = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    componentes_frete_json = models.JSONField(default=list, blank=True)

    icms_base = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    icms_aliquota = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'))
    icms_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    modal = models.CharField(max_length=16, blank=True)
    tipo_servico = models.CharField(max_length=16, blank=True)
    municipio_inicio = models.CharField(max_length=120, blank=True)
    uf_inicio = models.CharField(max_length=2, blank=True)
    municipio_fim = models.CharField(max_length=120, blank=True)
    uf_fim = models.CharField(max_length=2, blank=True)

    # Participantes (JSON fiel ao XML)
    emit_json = models.JSONField(default=dict, blank=True)
    rem_json = models.JSONField(default=dict, blank=True)
    dest_json = models.JSONField(default=dict, blank=True)
    exped_json = models.JSONField(default=dict, blank=True)
    receb_json = models.JSONField(default=dict, blank=True)
    tomador_json = models.JSONField(default=dict, blank=True)

    totais_json = models.JSONField(default=dict, blank=True)
    imposto_json = models.JSONField(default=dict, blank=True)
    prot_json = models.JSONField(default=dict, blank=True)
    reforma_e_outros_json = models.JSONField(default=dict, blank=True)

    chaves_nfe_vinculadas = models.JSONField(default=list, blank=True)

    transportadora = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados',
    )
    empresa_tomadora = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_tomadora',
    )
    empresa_destinataria = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_destinataria',
    )
    empresa_recebedora = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_recebedora',
    )
    fornecedor_remetente = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctes_historicos_importados_como_remetente',
    )
    papel_empresa_no_documento = models.CharField(max_length=32, blank=True)

    importado = models.BooleanField(default=True)
    origem_externa = models.BooleanField(default=True)
    historico = models.BooleanField(default=True)

    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dh_emissao', '-id']
        verbose_name = 'CT-e importado (histórico)'
        verbose_name_plural = 'CT-e importados (histórico)'

    def __str__(self):
        return f'{self.chave_acesso} — {self.numero}/{self.serie}'


class EventoCTeHistoricoImportado(models.Model):
    """
    Estrutura pronta para eventos do CT-e (cancelamento, etc).
    Nesta fase, o XML de evento pode não ser importado, mas a base já fica preparada.
    """

    cte = models.ForeignKey(
        CTeHistoricoImportado,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    chave_acesso = models.CharField(max_length=44, db_index=True)
    tipo_evento = models.CharField(max_length=16, db_index=True)
    protocolo_evento = models.CharField(max_length=30, blank=True)
    id_evento = models.CharField(max_length=80, blank=True)
    sequencial_evento = models.PositiveSmallIntegerField(default=0)
    data_evento = models.DateTimeField(null=True, blank=True)
    evento_json = models.JSONField(default=dict, blank=True)
    nome_arquivo = models.CharField(max_length=255, blank=True)
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-importado_em', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['cte', 'tipo_evento', 'protocolo_evento', 'id_evento'],
                name='uniq_cte_hist_evento_dedup',
            )
        ]


class NFeSefazStatusConsulta(models.Model):
    """NF-e 3.6 — registro de consulta status_servico SEFAZ (homologação/produção)."""

    class Ambiente(models.TextChoices):
        HOMOLOGACAO = 'homologacao', 'Homologação'
        PRODUCAO = 'producao', 'Produção'

    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.CASCADE,
        related_name='consultas_status_sefaz',
    )
    uf = models.CharField(max_length=2, default='SP')
    ambiente = models.CharField(max_length=16, choices=Ambiente.choices, default=Ambiente.HOMOLOGACAO)
    modelo = models.CharField(max_length=8, default='nfe')
    sucesso = models.BooleanField(default=False)
    c_stat = models.CharField(max_length=8, blank=True)
    x_motivo = models.TextField(blank=True)
    ver_aplic = models.CharField(max_length=64, blank=True)
    tp_amb = models.CharField(max_length=2, blank=True)
    c_uf = models.CharField(max_length=4, blank=True)
    dh_recbto = models.CharField(max_length=40, blank=True)
    t_med = models.CharField(max_length=16, blank=True)
    versao_retorno = models.CharField(max_length=8, blank=True)
    servico_operacional = models.BooleanField(default=False)
    certificado_valido = models.BooleanField(default=False)
    certificado_cnpj = models.CharField(max_length=20, blank=True)
    certificado_validade_fim = models.DateField(null=True, blank=True)
    xml_resposta = models.TextField(blank=True)
    raw_response = models.TextField(blank=True)
    erro_tecnico = models.TextField(blank=True)
    tipo_erro = models.CharField(max_length=32, blank=True)
    traceback_resumido = models.TextField(blank=True)
    mensagens = models.JSONField(default=list, blank=True)
    consultado_em = models.DateTimeField(auto_now_add=True)
    consultado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consultas_status_sefaz_nfe',
    )

    class Meta:
        ordering = ['-consultado_em', '-id']
        verbose_name = 'Consulta status SEFAZ NF-e'
        verbose_name_plural = 'Consultas status SEFAZ NF-e'

    def __str__(self):
        return f'{self.empresa_id} {self.uf} {self.ambiente} cStat={self.c_stat or "—"}'
