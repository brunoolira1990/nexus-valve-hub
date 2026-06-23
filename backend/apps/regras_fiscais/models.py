from django.db import models


class RegraFiscal(models.Model):
    class Operacao(models.TextChoices):
        ENTRADA = 'Entrada', 'Entrada'
        SAIDA = 'Saída', 'Saída'

    ncm = models.CharField(max_length=16)
    uf_origem = models.CharField(max_length=2)
    uf_destino = models.CharField(max_length=2)
    operacao = models.CharField(max_length=16, choices=Operacao.choices)
    cfop = models.CharField(max_length=8)
    cst_icms = models.CharField(max_length=8, blank=True)
    aliquota_icms = models.FloatField(default=0)
    cst_pis = models.CharField(max_length=8, blank=True)
    aliquota_pis = models.FloatField(default=0)
    cst_cofins = models.CharField(max_length=8, blank=True)
    aliquota_cofins = models.FloatField(default=0)
    cst_ipi = models.CharField(max_length=8, blank=True)
    aliquota_ipi = models.FloatField(default=0)
    base_calculo = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['ncm', 'uf_origem', 'uf_destino']
        indexes = [
            models.Index(fields=['ncm', 'uf_origem', 'uf_destino', 'operacao']),
        ]

    def __str__(self):
        return f'{self.ncm} {self.uf_origem}->{self.uf_destino} {self.operacao}'


class CenarioFiscalEntrada(models.Model):
    """Container operacional de configurações fiscais de entrada (modelo Nexus)."""

    nome = models.CharField(max_length=120)
    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cenarios_fiscais_entrada',
    )
    regime_tributario = models.CharField(max_length=64, blank=True)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(
        default=False,
        help_text='Cenário usado na conferência quando nenhum outro é informado.',
    )
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-padrao', 'nome', 'id']
        verbose_name = 'Cenário fiscal de entrada'
        verbose_name_plural = 'Cenários fiscais de entrada'

    def __str__(self) -> str:
        return self.nome


class CenarioFiscalEntradaEscopo(models.Model):
    """Agrupa NCM, produto ou regra geral dentro de um cenário."""

    class TipoEscopo(models.TextChoices):
        GERAL = 'GERAL', 'Regra geral'
        NCM = 'NCM', 'NCM'
        NCM_PREFIXO = 'NCM_PREFIXO', 'NCM por prefixo'
        PRODUTO = 'PRODUTO', 'Produto específico'

    cenario = models.ForeignKey(
        CenarioFiscalEntrada,
        on_delete=models.CASCADE,
        related_name='escopos',
    )
    tipo_escopo = models.CharField(max_length=16, choices=TipoEscopo.choices)
    ncm = models.CharField(max_length=16, blank=True)
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escopos_fiscais_entrada',
    )
    prioridade_escopo = models.IntegerField(default=10)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tipo_escopo', 'ncm', 'produto_id', 'id']
        verbose_name = 'Escopo do cenário fiscal de entrada'
        verbose_name_plural = 'Escopos do cenário fiscal de entrada'
        constraints = [
            models.UniqueConstraint(
                fields=['cenario', 'tipo_escopo', 'ncm', 'produto'],
                name='uniq_cenario_fiscal_entrada_escopo',
            ),
        ]

    def __str__(self) -> str:
        from apps.regras_fiscais.cenario_fiscal_entrada import label_escopo

        return label_escopo(self)


class RegraFiscalEntrada(models.Model):
    """Configuração folha (UF/CFOP/impostos) para conferência de NF-e de entrada."""

    class Severidade(models.TextChoices):
        INFORMATIVO = 'INFORMATIVO', 'Informativo'
        ALERTA = 'ALERTA', 'Alerta'
        BLOQUEIO = 'BLOQUEIO', 'Bloqueio'

    class TipoOperacaoFiscal(models.TextChoices):
        COMPRA = 'COMPRA', 'Compra'
        DEVOLUCAO_VENDA = 'DEVOLUCAO_VENDA', 'Devolução de venda'
        DEVOLUCAO_COMPRA = 'DEVOLUCAO_COMPRA', 'Devolução de compra'
        REMESSA = 'REMESSA', 'Remessa'
        BONIFICACAO = 'BONIFICACAO', 'Bonificação'
        USO_CONSUMO = 'USO_CONSUMO', 'Uso e consumo'
        INDUSTRIALIZACAO = 'INDUSTRIALIZACAO', 'Industrialização'
        OUTROS = 'OUTROS', 'Outros'

    cenario = models.ForeignKey(
        CenarioFiscalEntrada,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configuracoes',
    )
    escopo = models.ForeignKey(
        CenarioFiscalEntradaEscopo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configuracoes',
    )

    nome = models.CharField(max_length=120)
    codigo = models.CharField(max_length=32, blank=True)
    ativo = models.BooleanField(default=True)
    prioridade = models.IntegerField(default=0)

    cfop = models.CharField(
        max_length=8,
        blank=True,
        help_text='Legado: espelha cfop_origem na fase de transição.',
    )
    cfop_origem = models.CharField(
        max_length=8,
        blank=True,
        help_text='CFOP informado na NF-e (origem da operação).',
    )
    cfop_entrada = models.CharField(
        max_length=8,
        blank=True,
        help_text='CFOP de entrada/classificação esperado após conferência.',
    )
    descricao_cenario = models.CharField(
        max_length=255,
        blank=True,
        help_text='Rótulo da configuração (gerado automaticamente).',
    )
    ncm = models.CharField(max_length=16, blank=True)
    ncm_prefixo = models.BooleanField(default=False)
    uf_origem = models.CharField(max_length=2, blank=True)
    uf_destino = models.CharField(max_length=2, blank=True)
    tipo_operacao_fiscal = models.CharField(
        max_length=32,
        choices=TipoOperacaoFiscal.choices,
        blank=True,
    )

    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regras_fiscais_entrada',
    )
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regras_fiscais_entrada',
    )

    cst_icms_esperado = models.CharField(max_length=8, blank=True)
    csosn_esperado = models.CharField(max_length=8, blank=True)
    cst_pis_esperado = models.CharField(max_length=8, blank=True)
    cst_cofins_esperado = models.CharField(max_length=8, blank=True)
    cst_ipi_esperado = models.CharField(max_length=8, blank=True)

    modalidade_bc_icms = models.CharField(max_length=8, blank=True)
    aliquota_icms = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_bc_icms = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    motivo_desoneracao_icms = models.CharField(max_length=8, blank=True)
    codigo_beneficio_icms = models.CharField(max_length=16, blank=True)
    icms_st_aplicavel = models.BooleanField(null=True, blank=True)
    cst_icms_st_esperado = models.CharField(max_length=8, blank=True)
    aliquota_icms_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    mva_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_bc_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)

    fcp_aplicavel = models.BooleanField(null=True, blank=True)
    aliquota_fcp = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    aliquota_fcp_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_bc_fcp = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_fcp_unidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    reforma_tributaria = models.JSONField(null=True, blank=True)

    tipo_calculo_ipi = models.CharField(max_length=8, blank=True)
    aliquota_ipi = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_ipi_unidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    enquadramento_ipi = models.CharField(max_length=8, blank=True)

    tipo_calculo_pis = models.CharField(max_length=8, blank=True)
    aliquota_pis = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_base_pis = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_minimo_pis_unidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    aliquota_pis_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)

    tipo_calculo_cofins = models.CharField(max_length=8, blank=True)
    aliquota_cofins = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_base_cofins = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_minimo_cofins_unidade = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
    )
    aliquota_cofins_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)

    movimenta_estoque = models.BooleanField(default=True)
    exige_certificado_fornecedor = models.BooleanField(default=False)
    permite_credito_fiscal = models.BooleanField(default=True)

    severidade = models.CharField(
        max_length=16,
        choices=Severidade.choices,
        default=Severidade.INFORMATIVO,
    )
    mensagem_padrao = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-prioridade', 'nome', 'id']
        verbose_name = 'Regra fiscal de entrada'
        verbose_name_plural = 'Regras fiscais de entrada'
        indexes = [
            models.Index(fields=['ativo', '-prioridade']),
            models.Index(fields=['cfop']),
            models.Index(fields=['cfop_origem']),
            models.Index(fields=['ncm']),
            models.Index(fields=['cenario', 'escopo', 'ativo']),
        ]

    def _sync_cfop_compat(self) -> None:
        """Mantém cfop legado alinhado a cfop_origem durante a transição de API."""
        origem = (self.cfop_origem or '').strip()
        legado = (self.cfop or '').strip()
        if origem:
            self.cfop = origem
        elif legado:
            self.cfop_origem = legado

    def save(self, *args, **kwargs):
        from apps.regras_fiscais.cenario_fiscal_entrada import associar_cenario_e_escopo_regra

        self._sync_cfop_compat()
        associar_cenario_e_escopo_regra(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            (self.descricao_cenario or '').strip()
            or self.nome
            or self.codigo
            or f'Regra entrada #{self.pk}'
        )


class CenarioFiscalSaida(models.Model):
    """Container de configurações fiscais de saída (emissão / propostas — fase estrutural)."""

    nome = models.CharField(max_length=120)
    empresa = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cenarios_fiscais_saida',
    )
    regime_tributario = models.CharField(max_length=64, blank=True)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(
        default=False,
        help_text='Cenário usado por padrão quando nenhum outro for informado.',
    )
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-padrao', 'nome', 'id']
        verbose_name = 'Cenário fiscal de saída'
        verbose_name_plural = 'Cenários fiscais de saída'

    def __str__(self) -> str:
        return self.nome


class CenarioFiscalSaidaEscopo(models.Model):
    """Agrupa NCM, produto ou regra geral dentro de um cenário de saída."""

    class TipoEscopo(models.TextChoices):
        GERAL = 'GERAL', 'Regra geral'
        NCM = 'NCM', 'NCM'
        NCM_PREFIXO = 'NCM_PREFIXO', 'NCM por prefixo'
        PRODUTO = 'PRODUTO', 'Produto específico'

    cenario = models.ForeignKey(
        CenarioFiscalSaida,
        on_delete=models.CASCADE,
        related_name='escopos',
    )
    tipo_escopo = models.CharField(max_length=16, choices=TipoEscopo.choices)
    ncm = models.CharField(max_length=16, blank=True)
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escopos_fiscais_saida',
    )
    prioridade_escopo = models.IntegerField(default=10)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tipo_escopo', 'ncm', 'produto_id', 'id']
        verbose_name = 'Escopo do cenário fiscal de saída'
        verbose_name_plural = 'Escopos do cenário fiscal de saída'
        constraints = [
            models.UniqueConstraint(
                fields=['cenario', 'tipo_escopo', 'ncm', 'produto'],
                name='uniq_cenario_fiscal_saida_escopo',
            ),
        ]

    def __str__(self) -> str:
        from apps.regras_fiscais.cenario_fiscal_saida import label_escopo_saida

        return label_escopo_saida(self)


class RegraFiscalSaida(models.Model):
    """Configuração folha de impostos de saída (CFOP venda, tributos, efeitos operacionais)."""

    class DestinatarioContribuinte(models.TextChoices):
        CONTRIBUINTE = 'CONTRIBUINTE', 'Contribuinte'
        NAO_CONTRIBUINTE = 'NAO_CONTRIBUINTE', 'Não contribuinte'
        QUALQUER = 'QUALQUER', 'Qualquer'

    class TipoOperacao(models.TextChoices):
        VENDA = 'VENDA', 'Venda'
        DEVOLUCAO = 'DEVOLUCAO', 'Devolução'
        REMESSA = 'REMESSA', 'Remessa'
        BONIFICACAO = 'BONIFICACAO', 'Bonificação'
        INDUSTRIALIZACAO = 'INDUSTRIALIZACAO', 'Industrialização'
        OUTROS = 'OUTROS', 'Outros'

    cenario = models.ForeignKey(
        CenarioFiscalSaida,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configuracoes',
    )
    escopo = models.ForeignKey(
        CenarioFiscalSaidaEscopo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configuracoes',
    )

    nome = models.CharField(max_length=120, blank=True)
    codigo = models.CharField(max_length=32, blank=True)
    ativo = models.BooleanField(default=True)
    prioridade = models.IntegerField(default=0)

    uf_origem = models.CharField(max_length=2, blank=True)
    uf_destino = models.CharField(max_length=2, blank=True)
    destinatario_contribuinte = models.CharField(
        max_length=20,
        choices=DestinatarioContribuinte.choices,
        default=DestinatarioContribuinte.QUALQUER,
    )
    consumidor_final = models.BooleanField(null=True, blank=True)
    cfop_venda = models.CharField(max_length=8, blank=True)
    cfop_venda_st = models.CharField(max_length=8, blank=True)
    tipo_operacao = models.CharField(
        max_length=32,
        choices=TipoOperacao.choices,
        blank=True,
    )
    descricao_cenario = models.CharField(
        max_length=255,
        blank=True,
        help_text='Rótulo da configuração (gerado automaticamente).',
    )

    cst_icms = models.CharField(max_length=8, blank=True)
    csosn = models.CharField(max_length=8, blank=True)
    modalidade_bc_icms = models.CharField(max_length=8, blank=True)
    aliquota_icms = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_bc_icms = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    motivo_desoneracao_icms = models.CharField(max_length=8, blank=True)
    codigo_beneficio_icms = models.CharField(max_length=16, blank=True)
    icms_st_aplicavel = models.BooleanField(null=True, blank=True)
    cst_icms_st = models.CharField(max_length=8, blank=True)
    aliquota_icms_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    mva_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_bc_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)

    difal_aplicavel = models.BooleanField(
        null=True,
        blank=True,
        help_text='Calcula DIFAL/ICMSUFDest em venda interestadual a consumidor final não contribuinte.',
    )
    aliquota_icms_interestadual = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Alíquota interestadual (pICMSInter) para DIFAL.',
    )
    aliquota_icms_interna_destino = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Alíquota interna da UF destino (pICMSUFDest) para DIFAL.',
    )

    fcp_aplicavel = models.BooleanField(null=True, blank=True)
    aliquota_fcp = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    aliquota_fcp_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_bc_fcp = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_fcp_unidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    reforma_tributaria = models.JSONField(null=True, blank=True)

    cst_ipi = models.CharField(max_length=8, blank=True)
    tipo_calculo_ipi = models.CharField(max_length=8, blank=True)
    aliquota_ipi = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_ipi_unidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    enquadramento_ipi = models.CharField(max_length=8, blank=True)

    cst_pis = models.CharField(max_length=8, blank=True)
    tipo_calculo_pis = models.CharField(max_length=8, blank=True)
    aliquota_pis = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_base_pis = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_minimo_pis_unidade = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    aliquota_pis_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    deduzir_icms_base_pis = models.BooleanField(default=False)

    cst_cofins = models.CharField(max_length=8, blank=True)
    tipo_calculo_cofins = models.CharField(max_length=8, blank=True)
    aliquota_cofins = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    reducao_base_cofins = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    valor_minimo_cofins_unidade = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
    )
    aliquota_cofins_st = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    deduzir_icms_base_cofins = models.BooleanField(default=False)

    movimenta_estoque = models.BooleanField(default=True)
    gera_financeiro = models.BooleanField(default=True)
    informacoes_complementares = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    recomendacoes_nfe = models.JSONField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-prioridade', 'nome', 'id']
        verbose_name = 'Regra fiscal de saída'
        verbose_name_plural = 'Regras fiscais de saída'
        indexes = [
            models.Index(fields=['ativo', '-prioridade']),
            models.Index(fields=['cfop_venda']),
            models.Index(fields=['cenario', 'escopo', 'ativo']),
        ]

    def save(self, *args, **kwargs):
        from apps.regras_fiscais.cenario_fiscal_saida import associar_cenario_e_escopo_regra_saida

        associar_cenario_e_escopo_regra_saida(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            (self.descricao_cenario or '').strip()
            or (self.nome or '').strip()
            or self.codigo
            or f'Regra saída #{self.pk}'
        )
