"""Equivalência, composição e montagem de produtos — ERP 4.0.13.7 / 4.0.13.7.1."""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class TipoComposicaoProduto(models.TextChoices):
    KIT_COMERCIAL = 'KIT_COMERCIAL', 'Kit comercial'
    MONTAGEM_SIMPLES = 'MONTAGEM_SIMPLES', 'Montagem simples'
    MONTAGEM_ROSCADA = 'MONTAGEM_ROSCADA', 'Montagem roscada'
    MONTAGEM_SOLDADA = 'MONTAGEM_SOLDADA', 'Montagem soldada'
    MONTAGEM_SERVICO_INTERNO = 'MONTAGEM_SERVICO_INTERNO', 'Montagem com serviço interno'
    MONTAGEM_TERCEIRIZADA = 'MONTAGEM_TERCEIRIZADA', 'Montagem terceirizada'
    BENEFICIAMENTO = 'BENEFICIAMENTO', 'Beneficiamento'


class TipoProcessoMontagem(models.TextChoices):
    ENCAIXE = 'encaixe', 'Encaixe'
    ROSCA = 'rosca', 'Rosca'
    FLANGEAMENTO = 'flangeamento', 'Flangeamento'
    SOLDA = 'solda', 'Solda'
    CORTE = 'corte', 'Corte'
    USINAGEM = 'usinagem', 'Usinagem'
    MONTAGEM_MANUAL = 'montagem_manual', 'Montagem manual'
    MONTAGEM_TERCEIRIZADA = 'montagem_terceirizada', 'Montagem terceirizada'
    OUTRO = 'outro', 'Outro'


class OrigemEquivalencia(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    SUGESTAO_CONFIRMADA = 'sugestao_confirmada', 'Sugestão confirmada'
    IMPORTACAO_HISTORICA = 'importacao_historica', 'Importação histórica'


class EscopoCnpjFornecedor(models.TextChoices):
    FILIAL = 'filial', 'Somente filial'
    RAIZ = 'raiz', 'CNPJ raiz'
    FORNECEDOR = 'fornecedor', 'Fornecedor cadastrado'


class ProdutoComposicao(models.Model):
    produto_final = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.CASCADE,
        related_name='composicoes',
    )
    nome = models.CharField(max_length=120, blank=True)
    tipo_composicao = models.CharField(max_length=40, choices=TipoComposicaoProduto.choices)
    descricao = models.CharField(max_length=255, blank=True)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    permite_alternativa = models.BooleanField(default=True)
    permite_comprar_pronto = models.BooleanField(default=True)
    permite_montar = models.BooleanField(default=True)
    exige_ordem_montagem = models.BooleanField(default=False)
    exige_confirmacao = models.BooleanField(default=True)
    exige_servico = models.BooleanField(default=False)
    tipo_servico = models.CharField(max_length=64, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['produto_final_id', '-padrao', '-ativo', 'id']
        verbose_name = 'Composição de produto'
        verbose_name_plural = 'Composições de produto'

    def __str__(self) -> str:
        rotulo = self.nome or self.get_tipo_composicao_display()
        return f'{self.produto_final_id} — {rotulo}'


class ProdutoComposicaoItem(models.Model):
    composicao = models.ForeignKey(
        ProdutoComposicao,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    componente_produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.PROTECT,
        related_name='composicoes_como_componente',
    )
    quantidade_por_unidade_final = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('1'))
    unidade = models.CharField(max_length=16, blank=True)
    obrigatorio = models.BooleanField(default=True)
    permite_substituto = models.BooleanField(default=False)
    perda_percentual = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['composicao_id', 'ordem', 'id']

    def __str__(self) -> str:
        return f'{self.composicao_id} → {self.componente_produto_id}'


class ProcessoMontagem(models.Model):
    """Processo cadastral/informativo — não executa estoque nesta fase."""

    composicao = models.ForeignKey(
        ProdutoComposicao,
        on_delete=models.CASCADE,
        related_name='processos',
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=32, choices=TipoProcessoMontagem.choices)
    exige_servico = models.BooleanField(default=False)
    exige_fornecedor_servico = models.BooleanField(default=False)
    gera_produto_acabado = models.BooleanField(default=True)
    baixa_componentes = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['composicao_id', 'id']

    def __str__(self) -> str:
        return self.get_tipo_display()


class FornecedorProdutoEquivalencia(models.Model):
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.CASCADE,
        related_name='equivalencias_produto',
    )
    cnpj_raiz_fornecedor = models.CharField(max_length=8, blank=True, db_index=True)
    cnpj_filial_fornecedor = models.CharField(max_length=14, blank=True, db_index=True)
    escopo_cnpj = models.CharField(
        max_length=16,
        choices=EscopoCnpjFornecedor.choices,
        default=EscopoCnpjFornecedor.RAIZ,
    )
    produto_interno = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.CASCADE,
        related_name='equivalencias_fornecedor',
    )
    codigo_fornecedor = models.CharField(max_length=64, blank=True, db_index=True)
    descricao_fornecedor_normalizada = models.CharField(max_length=512, blank=True, db_index=True)
    ncm_fornecedor = models.CharField(max_length=8, blank=True)
    unidade_fornecedor = models.CharField(max_length=16, blank=True)
    fator_conversao = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('1'))
    tolerancia_quantidade = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.01'))
    tolerancia_valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.05'))
    ativo = models.BooleanField(default=True)
    confianca_padrao = models.PositiveSmallIntegerField(default=90)
    origem = models.CharField(max_length=32, choices=OrigemEquivalencia.choices, default=OrigemEquivalencia.MANUAL)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fornecedor_id', 'codigo_fornecedor', 'id']
        indexes = [
            models.Index(fields=['fornecedor', 'codigo_fornecedor']),
            models.Index(fields=['cnpj_raiz_fornecedor', 'codigo_fornecedor']),
        ]

    def __str__(self) -> str:
        return f'{self.codigo_fornecedor} → {self.produto_interno_id}'


class FornecedorComposicaoEquivalencia(models.Model):
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.CASCADE,
        related_name='equivalencias_composicao',
    )
    cnpj_raiz_fornecedor = models.CharField(max_length=8, blank=True, db_index=True)
    cnpj_filial_fornecedor = models.CharField(max_length=14, blank=True, db_index=True)
    escopo_cnpj = models.CharField(
        max_length=16,
        choices=EscopoCnpjFornecedor.choices,
        default=EscopoCnpjFornecedor.RAIZ,
    )
    produto_interno_final = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.CASCADE,
        related_name='equivalencias_composicao_fornecedor',
    )
    descricao = models.CharField(max_length=255, blank=True)
    tolerancia_valor_percentual = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0.5'))
    tolerancia_valor_absoluto = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.05'))
    tolerancia_quantidade = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.01'))
    ativo = models.BooleanField(default=True)
    origem = models.CharField(max_length=32, choices=OrigemEquivalencia.choices, default=OrigemEquivalencia.MANUAL)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fornecedor_id', 'produto_interno_final_id', 'id']

    def __str__(self) -> str:
        return f'Composta {self.produto_interno_final_id} ({self.fornecedor_id})'


class FornecedorComposicaoEquivalenciaItem(models.Model):
    equivalencia_composta = models.ForeignKey(
        FornecedorComposicaoEquivalencia,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    codigo_fornecedor = models.CharField(max_length=64, blank=True)
    descricao_fornecedor_normalizada = models.CharField(max_length=512, blank=True)
    ncm_fornecedor = models.CharField(max_length=8, blank=True)
    produto_componente_interno = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equivalencias_composicao_componente',
    )
    quantidade_componente_por_produto_final = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal('1'),
    )
    unidade = models.CharField(max_length=16, blank=True)
    obrigatorio = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    peso_match_codigo = models.PositiveSmallIntegerField(default=40)
    peso_match_descricao = models.PositiveSmallIntegerField(default=25)
    peso_match_ncm = models.PositiveSmallIntegerField(default=15)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['equivalencia_composta_id', 'ordem', 'id']

    def __str__(self) -> str:
        return self.codigo_fornecedor or self.descricao_fornecedor_normalizada[:40]
