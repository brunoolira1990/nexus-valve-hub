from decimal import Decimal

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
    numero = models.CharField(max_length=64)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.PROTECT,
        related_name='nf_saidas',
    )
    data = models.DateField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
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

    class Meta:
        ordering = ['-data', 'numero']
        verbose_name = 'NF saída'


class ItemNFeSaida(models.Model):
    nf = models.ForeignKey(NFeSaida, on_delete=models.CASCADE, related_name='itens')
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
