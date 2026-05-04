from decimal import Decimal

from django.db import models


def _norm_polegada(polegada: str) -> str:
    return (polegada or '').replace('"', '').strip()


class Ncm(models.Model):
    codigo = models.CharField(max_length=16, unique=True)
    descricao = models.CharField(max_length=512, blank=True)
    aliquota_ipi = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    ex_tipi = models.CharField(max_length=16, blank=True)
    vigencia_inicio = models.DateField(null=True, blank=True)
    vigencia_fim = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    fonte = models.CharField(max_length=64, blank=True)
    observacoes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'NCM'

    def __str__(self):
        return self.codigo


class Polegada(models.Model):
    """Cadastro mestre de polegadas com código oficial operacional."""

    codigo = models.CharField(max_length=4, unique=True)
    codigo_oficial = models.CharField(max_length=8, unique=True, null=True, blank=True)
    descricao = models.CharField(max_length=64)
    valor_decimal = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    valor_mm = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    ativo = models.BooleanField(default=True)
    origem = models.CharField(max_length=32, blank=True)
    observacoes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['valor_decimal', 'codigo_oficial']
        verbose_name = 'Polegada'

    def __str__(self):
        return f'{self.codigo_oficial} — {self.descricao}'

    def save(self, *args, **kwargs):
        if self.valor_mm is None and self.valor_decimal is not None:
            self.valor_mm = (self.valor_decimal * Decimal('25.4')).quantize(Decimal('0.001'))
        if not self.codigo_oficial:
            self.codigo_oficial = self.codigo
        if not self.codigo:
            self.codigo = self.codigo_oficial
        super().save(*args, **kwargs)


class RoscaConexao(models.Model):
    """Rosca / conexão (antigo conceito de sufixo no código interno)."""

    codigo = models.CharField(
        max_length=16,
        unique=True,
        help_text='Código no produto (ex.: N, S). Vazio = BSP / padrão da família.',
    )
    descricao = models.CharField(max_length=128)
    observacao = models.CharField(max_length=256, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Rosca / Conexão'
        verbose_name_plural = 'Roscas / Conexões'

    def __str__(self):
        return f'{self.codigo or "∅"} — {self.descricao}'


class ScheduleEspessura(models.Model):
    codigo_schedule = models.CharField(max_length=32, unique=True)
    descricao = models.CharField(max_length=128, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo_schedule']
        verbose_name = 'Schedule / Espessura'

    def __str__(self):
        return f'{self.codigo_schedule} — {self.descricao}'


class FamiliaProduto(models.Model):
    """Família / figura base para geração de código interno."""

    class TipoRegraCodigo(models.TextChoices):
        BASE_POLEGADA = 'BASE_POLEGADA', 'Base + polegada principal'
        BASE_ROSCA_POLEGADA = 'BASE_ROSCA_POLEGADA', 'Base + rosca/conexão + polegada principal'
        BASE_DUAS_POLEGADAS = 'BASE_DUAS_POLEGADAS', 'Base + duas polegadas (IDs)'
        BASE_ROSCA_DUAS_POLEGADAS = 'BASE_ROSCA_DUAS_POLEGADAS', 'Base + rosca + duas polegadas'
        BASE_SCHEDULE_POLEGADA = 'BASE_SCHEDULE_POLEGADA', 'Base + schedule + polegada principal'
        BASE_SCHEDULE_DUAS_POLEGADAS = 'BASE_SCHEDULE_DUAS_POLEGADAS', 'Base + schedule + duas polegadas'
        BASE_ROSCA_SCHEDULE_POLEGADA = 'BASE_ROSCA_SCHEDULE_POLEGADA', 'Base + rosca + schedule + polegada principal'
        BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS = (
            'BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS',
            'Base + rosca + schedule + duas polegadas',
        )
        UNDERSCORE_POLEGADA = 'UNDERSCORE_POLEGADA', 'Base + underscore + ID polegada (3 dígitos)'
        MANUAL_FABRICANTE = 'MANUAL_FABRICANTE', 'Manual / fabricante (sem código automático por família)'

    class TipoControleUnidade(models.TextChoices):
        PECA = 'PECA', 'Peça'
        DIMENSIONAL = 'DIMENSIONAL', 'Dimensional'
        PESO = 'PESO', 'Peso'
        LINEAR = 'LINEAR', 'Linear'
        LINEAR_PESO = 'LINEAR_PESO', 'Linear + Peso'
        CHAPA = 'CHAPA', 'Chapa'
        TUBO = 'TUBO', 'Tubo'
        BARRA = 'BARRA', 'Barra'
        PERFIL = 'PERFIL', 'Perfil'

    class TipoFisico(models.TextChoices):
        PECA = 'PECA', 'Peça'
        TUBO = 'TUBO', 'Tubo'
        BARRA_REDONDA = 'BARRA_REDONDA', 'Barra redonda'
        BARRA_CHATA = 'BARRA_CHATA', 'Barra chata'
        BARRA_SEXTAVADA = 'BARRA_SEXTAVADA', 'Barra sextavada'
        CHAPA = 'CHAPA', 'Chapa'
        DISCO = 'DISCO', 'Disco'
        PERFIL = 'PERFIL', 'Perfil'
        CANTONEIRA = 'CANTONEIRA', 'Cantoneira'
        OUTRO = 'OUTRO', 'Outro'

    codigo_figura = models.CharField(max_length=32, unique=True)
    descricao_base = models.CharField(max_length=512)
    tipo_regra_codigo = models.CharField(
        max_length=48,
        choices=TipoRegraCodigo.choices,
        default=TipoRegraCodigo.BASE_POLEGADA,
    )
    usa_rosca_conexao = models.BooleanField(default=False)
    usa_schedule = models.BooleanField(default=False)
    usa_polegada_principal = models.BooleanField(default=True)
    usa_polegada_secundaria = models.BooleanField(default=False)
    separador_base_medidas = models.CharField(
        max_length=1,
        default='.',
        help_text='Separador entre prefixo (figura[+rosca][+schedule]) e parte de polegadas; use _ para padrão tipo 6038_005.',
    )
    ncm_padrao = models.ForeignKey(
        'produtos.Ncm',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='familias_padrao',
    )
    unidade_padrao = models.CharField(max_length=16, blank=True)
    material_base = models.CharField(max_length=128, blank=True)
    pressao_base = models.CharField(max_length=64, blank=True)
    norma_base = models.CharField(max_length=128, blank=True)
    conexao_base = models.CharField(max_length=128, blank=True)
    ativo = models.BooleanField(default=True)
    tipo_fisico = models.CharField(max_length=24, choices=TipoFisico.choices, default=TipoFisico.PECA)
    tipo_controle_unidade = models.CharField(
        max_length=24,
        choices=TipoControleUnidade.choices,
        default=TipoControleUnidade.PECA,
    )
    unidade_estoque_padrao = models.CharField(max_length=16, blank=True)
    unidade_venda_padrao = models.CharField(max_length=16, blank=True)
    unidade_compra_padrao = models.CharField(max_length=16, blank=True)
    unidade_fiscal_padrao = models.CharField(max_length=16, blank=True)
    unidades_venda_permitidas = models.JSONField(default=list, blank=True)
    unidades_compra_permitidas = models.JSONField(default=list, blank=True)
    comprimento_padrao_barra_m = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    peso_por_metro_kg = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    peso_por_peca_kg = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    peso_por_chapa_kg = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    densidade = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    usa_conversao_dimensional = models.BooleanField(default=False)
    observacoes_conversao = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ['codigo_figura']
        verbose_name = 'Família / Figura de produto'
        verbose_name_plural = 'Famílias / Figuras de produto'

    def __str__(self):
        return f'{self.codigo_figura} — {self.descricao_base[:48]}'

    def save(self, *args, **kwargs):
        from apps.produtos.familia_regra import aplicar_flags_derivadas_na_instancia

        aplicar_flags_derivadas_na_instancia(self)
        super().save(*args, **kwargs)


class Produto(models.Model):
    """Produto comercial; código por regra da família, legado ou manual."""

    class ModoCodigo(models.TextChoices):
        LEGADO = 'LEGADO', 'Legado (campos texto figura/sufixo/schedule/polegada)'
        INTERNO = 'INTERNO', 'Código interno por família e bases'
        MANUAL = 'MANUAL', 'Código manual / fabricante'

    modo_codigo = models.CharField(
        max_length=16,
        choices=ModoCodigo.choices,
        default=ModoCodigo.LEGADO,
        db_index=True,
    )
    familia = models.ForeignKey(
        FamiliaProduto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='produtos',
    )
    rosca_conexao = models.ForeignKey(
        RoscaConexao,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='produtos',
    )
    schedule_ref = models.ForeignKey(
        ScheduleEspessura,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='produtos',
    )
    polegada_principal_ref = models.ForeignKey(
        Polegada,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='produtos_principal',
    )
    polegada_secundaria_ref = models.ForeignKey(
        Polegada,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='produtos_secundaria',
    )

    figura = models.CharField(max_length=32, blank=True)
    sufixo = models.CharField(max_length=32, blank=True)
    schedule = models.CharField(max_length=32, blank=True)
    polegada_principal = models.CharField(max_length=32, blank=True)
    polegada_secundaria = models.CharField(max_length=32, blank=True)
    descricao = models.CharField(max_length=512)
    material = models.CharField(max_length=128, blank=True)
    tipo_peca = models.CharField(max_length=128, blank=True)
    pressao_nominal = models.CharField(max_length=64, blank=True)
    norma = models.CharField(max_length=128, blank=True)
    conexao = models.CharField(max_length=128, blank=True)
    ncm = models.CharField(max_length=16, blank=True)
    unidade = models.CharField(max_length=16, blank=True)
    ncm_especifico = models.CharField(max_length=16, blank=True)
    unidade_especifica = models.CharField(max_length=16, blank=True)
    preco_custo = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    preco_venda = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    estoque_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    codigo_completo = models.CharField(max_length=128, blank=True, db_index=True)
    tipo_controle_unidade = models.CharField(
        max_length=24,
        choices=FamiliaProduto.TipoControleUnidade.choices,
        blank=True,
    )
    tipo_fisico = models.CharField(max_length=24, choices=FamiliaProduto.TipoFisico.choices, blank=True)
    unidade_estoque = models.CharField(max_length=16, blank=True)
    unidade_venda_padrao = models.CharField(max_length=16, blank=True)
    unidade_compra_padrao = models.CharField(max_length=16, blank=True)
    unidade_fiscal = models.CharField(max_length=16, blank=True)
    unidades_venda_permitidas = models.JSONField(default=list, blank=True)
    unidades_compra_permitidas = models.JSONField(default=list, blank=True)
    observacoes_conversao = models.CharField(max_length=512, blank=True)
    comprimento_padrao_barra_m = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    peso_por_metro_kg = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    peso_por_peca_kg = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    peso_por_chapa_kg = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    densidade = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    usa_conversao_dimensional = models.BooleanField(default=False)

    class Meta:
        ordering = ['codigo_completo']

    def gerar_codigo_legado(self) -> str:
        """Monta código a partir dos campos texto (compatibilidade com cadastros antigos)."""
        partes: list[str] = []
        for x in (self.figura, self.sufixo, self.schedule):
            s = (x or '').strip()
            if s:
                partes.append(s)
        p1 = _norm_polegada(self.polegada_principal)
        p2 = _norm_polegada(self.polegada_secundaria)
        if p1 and p2:
            partes.append(f'{p1}x{p2}')
        elif p1:
            partes.append(p1)
        elif p2:
            partes.append(p2)
        return '.'.join(partes) if partes else ''

    def save(self, *args, **kwargs):
        from apps.produtos.codigo_produto import produto_aplicar_codigo_completo

        produto_aplicar_codigo_completo(self)
        super().save(*args, **kwargs)

    def _fallback_familia_attr(self, attr: str):
        # Campos herdados da família (ex.: unidade_estoque_padrao) não existem no modelo Produto;
        # getattr sem default quebrava a serialização da listagem GET /produtos/.
        value = getattr(self, attr, None)
        if isinstance(value, str):
            if value.strip():
                return value
        elif value is not None:
            return value
        if self.familia_id:
            return getattr(self.familia, attr, None)
        return value

    def get_tipo_controle_unidade_efetivo(self) -> str:
        return self._fallback_familia_attr('tipo_controle_unidade') or FamiliaProduto.TipoControleUnidade.PECA

    def get_tipo_fisico_efetivo(self) -> str:
        return self._fallback_familia_attr('tipo_fisico') or FamiliaProduto.TipoFisico.PECA

    def get_unidade_estoque_efetiva(self) -> str:
        return self._fallback_familia_attr('unidade_estoque') or self._fallback_familia_attr('unidade_estoque_padrao') or self.unidade

    def get_unidade_venda_efetiva(self) -> str:
        return self._fallback_familia_attr('unidade_venda_padrao') or self.unidade

    def get_unidade_compra_efetiva(self) -> str:
        return self._fallback_familia_attr('unidade_compra_padrao') or self.unidade

    def get_unidade_fiscal_efetiva(self) -> str:
        return self._fallback_familia_attr('unidade_fiscal') or self._fallback_familia_attr('unidade_fiscal_padrao') or self.unidade

    def get_unidades_venda_permitidas_efetivas(self) -> list[str]:
        own = self.unidades_venda_permitidas or []
        if own:
            return own
        if self.familia_id:
            return self.familia.unidades_venda_permitidas or []
        return []

    def get_unidades_compra_permitidas_efetivas(self) -> list[str]:
        own = self.unidades_compra_permitidas or []
        if own:
            return own
        if self.familia_id:
            return self.familia.unidades_compra_permitidas or []
        return []

    def get_comprimento_padrao_barra_m_efetivo(self):
        return self._fallback_familia_attr('comprimento_padrao_barra_m')

    def get_peso_por_metro_kg_efetivo(self):
        return self._fallback_familia_attr('peso_por_metro_kg')

    def get_peso_por_peca_kg_efetivo(self):
        return self._fallback_familia_attr('peso_por_peca_kg')

    def get_peso_por_chapa_kg_efetivo(self):
        return self._fallback_familia_attr('peso_por_chapa_kg')

    def get_densidade_efetiva(self):
        return self._fallback_familia_attr('densidade')

    def get_usa_conversao_dimensional_efetivo(self) -> bool:
        if self.usa_conversao_dimensional:
            return True
        if self.familia_id:
            return bool(self.familia.usa_conversao_dimensional)
        return False

    def get_ncm_efetivo(self):
        codigo = (self.ncm or '').strip()
        if codigo:
            ncm_obj = Ncm.objects.filter(codigo=codigo).first()
            if ncm_obj:
                return ncm_obj
            return type('NcmInline', (), {'id': None, 'codigo': codigo, 'descricao': ''})()
        if self.familia_id and self.familia.ncm_padrao_id:
            return self.familia.ncm_padrao
        return None

    def get_ncm_origem(self):
        if (self.ncm or '').strip():
            return 'produto'
        if self.familia_id and self.familia.ncm_padrao_id:
            return 'familia'
        return 'nao_definido'

    def get_ncm_efetivo_codigo(self) -> str:
        ncm = self.get_ncm_efetivo()
        return (getattr(ncm, 'codigo', '') or '').strip()


class FamiliaProdutoPolegadaPermitida(models.Model):
    class TipoPolegada(models.TextChoices):
        PRINCIPAL = 'principal', 'Principal'
        SECUNDARIA = 'secundaria', 'Secundária'
        AMBAS = 'ambas', 'Ambas'

    familia = models.ForeignKey(
        FamiliaProduto,
        on_delete=models.CASCADE,
        related_name='polegadas_permitidas',
    )
    polegada = models.ForeignKey(Polegada, on_delete=models.PROTECT, related_name='familias_permitidas')
    tipo = models.CharField(max_length=16, choices=TipoPolegada.choices, default=TipoPolegada.AMBAS)
    ordem = models.PositiveIntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['familia_id', 'ordem', 'polegada__codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['familia', 'polegada', 'tipo'],
                name='uq_familia_polegada_permitida_tipo',
            ),
        ]

    def __str__(self):
        return f'{self.familia.codigo_figura} - {self.polegada.codigo} ({self.tipo})'


class FamiliaProdutoRoscaConexaoPermitida(models.Model):
    familia = models.ForeignKey(
        FamiliaProduto,
        on_delete=models.CASCADE,
        related_name='roscas_permitidas',
    )
    rosca_conexao = models.ForeignKey(
        RoscaConexao,
        on_delete=models.PROTECT,
        related_name='familias_permitidas',
    )
    padrao_da_familia = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['familia_id', '-padrao_da_familia', 'rosca_conexao__codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['familia', 'rosca_conexao'],
                name='uq_familia_rosca_permitida',
            ),
            models.UniqueConstraint(
                fields=['familia'],
                condition=models.Q(padrao_da_familia=True),
                name='uq_familia_rosca_padrao_unica',
            ),
        ]

    def __str__(self):
        return f'{self.familia.codigo_figura} - {self.rosca_conexao.codigo or "∅"}'


class FamiliaProdutoSchedulePermitido(models.Model):
    familia = models.ForeignKey(
        FamiliaProduto,
        on_delete=models.CASCADE,
        related_name='schedules_permitidos',
    )
    schedule = models.ForeignKey(
        ScheduleEspessura,
        on_delete=models.PROTECT,
        related_name='familias_permitidas',
    )
    padrao_da_familia = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['familia_id', '-padrao_da_familia', 'schedule__codigo_schedule']
        constraints = [
            models.UniqueConstraint(
                fields=['familia', 'schedule'],
                name='uq_familia_schedule_permitido',
            ),
            models.UniqueConstraint(
                fields=['familia'],
                condition=models.Q(padrao_da_familia=True),
                name='uq_familia_schedule_padrao_unico',
            ),
        ]

    def __str__(self):
        return f'{self.familia.codigo_figura} - {self.schedule.codigo_schedule}'
