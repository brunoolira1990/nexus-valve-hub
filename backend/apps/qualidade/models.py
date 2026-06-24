from django.db import models
from django.db.models import Q
import re

_RE_CQ_NUMERO_AUTO = re.compile(r'^CQ-(\d{8})-(\d{4})$', re.I)
_RE_CQ_NUMERO_AUTO_COMPACTO = re.compile(r'^CQ(\d{8})(\d{4})$', re.I)


def _split_numero_serie(numero: str, serie: str) -> tuple[str, str]:
    n = (numero or '').strip()
    s = (serie or '').strip()
    if '/' in n:
        partes = [p.strip() for p in n.split('/') if p.strip()]
        if partes:
            n = partes[0]
            if len(partes) > 1 and not s:
                s = partes[1]
    return n, s


def _normalize_numero_cq(numero: str) -> str:
    cleaned = (numero or '').strip().upper().replace(' ', '').replace('-', '')
    while cleaned.startswith('CQCQ'):
        cleaned = cleaned[2:]
    if not cleaned:
        return ''
    if not cleaned.startswith('CQ'):
        cleaned = f'CQ{cleaned}'
    return cleaned


def is_numero_cq_formato_automatico(numero: str | None) -> bool:
    raw = (numero or '').strip().upper()
    if not raw:
        return False
    if _RE_CQ_NUMERO_AUTO.match(raw):
        return True
    compacto = _normalize_numero_cq(raw)
    return bool(_RE_CQ_NUMERO_AUTO_COMPACTO.match(compacto))


def formatar_numero_cq_exibicao(numero: str) -> str:
    """Exibe CQ-AAAAMMDD-NNNN para numeração automática; preserva legado (ex.: CQ300)."""
    raw = (numero or '').strip().upper()
    if not raw:
        return ''
    m = _RE_CQ_NUMERO_AUTO.match(raw)
    if m:
        return f'CQ-{m.group(1)}-{m.group(2)}'
    compacto = _normalize_numero_cq(raw)
    m2 = _RE_CQ_NUMERO_AUTO_COMPACTO.match(compacto)
    if m2:
        return f'CQ-{m2.group(1)}-{m2.group(2)}'
    return compacto


def normalizar_numero_cq_armazenamento(numero: str) -> str:
    """Normaliza número para persistência sem quebrar formato automático com hífens."""
    raw = (numero or '').strip()
    if not raw:
        return ''
    if is_numero_cq_formato_automatico(raw):
        return raw.upper()
    numero_base, _ = _split_numero_serie(raw, '')
    return _normalize_numero_cq(numero_base)


class Certificado(models.Model):
    nf_saida = models.OneToOneField(
        'fiscal.NFeSaida',
        on_delete=models.CASCADE,
        related_name='certificado',
    )
    arquivo = models.FileField(upload_to='certificados/%Y/%m/')
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-gerado_em']


class CertificadoQualidade(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'rascunho', 'Rascunho'
        EMITIDO = 'emitido', 'Emitido'
        CANCELADO = 'cancelado', 'Cancelado'

    class TipoCertificado(models.TextChoices):
        PADRAO_POR_NFE = 'PADRAO_POR_NFE', 'Padrão por NF-e'
        VALVULA_COMPONENTES = 'VALVULA_COMPONENTES', 'Válvula por componentes'

    numero = models.CharField(max_length=32, blank=True)
    serie = models.CharField(max_length=16, blank=True)
    cliente = models.ForeignKey(
        'cadastros.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_qualidade',
    )
    cliente_nome_snapshot = models.CharField(max_length=255, blank=True)
    cliente_cnpj_snapshot = models.CharField(max_length=32, blank=True)
    pedido_cliente = models.CharField(max_length=120, blank=True)
    nota_fiscal_numero = models.CharField(max_length=64, blank=True)
    nota_fiscal = models.ForeignKey(
        'fiscal.NFeSaida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_qualidade',
    )
    nota_fiscal_historica = models.ForeignKey(
        'fiscal.NFeSaidaHistoricaImportada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_qualidade',
    )
    data_emissao = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    texto_padrao = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RASCUNHO)
    tipo_certificado = models.CharField(
        max_length=32,
        choices=TipoCertificado.choices,
        default=TipoCertificado.PADRAO_POR_NFE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        constraints = [
            models.UniqueConstraint(
                fields=['numero', 'serie'],
                name='uq_certificado_qualidade_numero_serie',
                condition=~Q(numero=''),
            ),
        ]

    @property
    def numero_formatado(self) -> str:
        numero_base, serie_base = _split_numero_serie(self.numero, self.serie)
        numero_norm = formatar_numero_cq_exibicao(numero_base)
        if not numero_norm:
            return ''
        if serie_base:
            return f'{numero_norm}/{serie_base}'
        return numero_norm


class ItemCertificadoQualidade(models.Model):
    class TipoDadosTecnicos(models.TextChoices):
        PADRAO_ITEM = 'PADRAO_ITEM', 'Dados por item'
        VALVULA_COMPONENTES = 'VALVULA_COMPONENTES', 'Dados por componentes de válvula'

    certificado = models.ForeignKey(
        CertificadoQualidade,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    ordem = models.PositiveIntegerField(default=1)
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_certificado_qualidade',
    )
    codigo_produto = models.CharField(max_length=128, blank=True)
    descricao_material = models.CharField(max_length=512, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    unidade = models.CharField(max_length=16, blank=True)
    norma = models.CharField(max_length=128, blank=True)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    tipo_dados_tecnicos = models.CharField(
        max_length=32,
        choices=TipoDadosTecnicos.choices,
        default=TipoDadosTecnicos.PADRAO_ITEM,
    )
    ncm = models.CharField(max_length=16, blank=True)
    observacoes_item = models.TextField(blank=True)
    composicao_json = models.JSONField(default=dict, blank=True)
    ensaio_tracao_json = models.JSONField(default=dict, blank=True)
    ensaio_impacto_json = models.JSONField(default=dict, blank=True)
    certificado_fornecedor_origem_id = models.PositiveIntegerField(null=True, blank=True)
    item_certificado_fornecedor_origem_id = models.PositiveIntegerField(null=True, blank=True)
    fornecedor_nome_snapshot = models.CharField(max_length=255, blank=True)
    nf_entrada_snapshot = models.CharField(max_length=64, blank=True)
    codigo_item_fornecedor_snapshot = models.CharField(max_length=128, blank=True)
    descricao_item_fornecedor_snapshot = models.CharField(max_length=512, blank=True)
    numero_certificado_fornecedor_item_snapshot = models.CharField(max_length=64, blank=True)
    corrida_snapshot = models.CharField(max_length=64, blank=True)
    lote_snapshot = models.CharField(max_length=64, blank=True)
    produto_snapshot = models.JSONField(default=dict, blank=True)
    origem_rastreabilidade_tipo = models.CharField(max_length=64, blank=True)
    origem_status_tecnico = models.CharField(max_length=64, blank=True)
    origem_observacoes = models.TextField(blank=True)
    incluir_no_certificado = models.BooleanField(default=True)
    motivo_nao_inclusao = models.CharField(max_length=128, blank=True)
    observacao_nao_inclusao = models.TextField(blank=True)

    class Meta:
        ordering = ['ordem', 'id']


class ItemCertificadoQualidadeComponente(models.Model):
    item_certificado = models.ForeignKey(
        ItemCertificadoQualidade,
        on_delete=models.CASCADE,
        related_name='componentes',
    )
    ordem = models.PositiveIntegerField(default=1)
    nome_componente = models.CharField(max_length=120)
    descricao_componente = models.CharField(max_length=255, blank=True)
    norma = models.CharField(max_length=128, blank=True)
    corrida = models.CharField(max_length=64, blank=True)
    revisao_corrida = models.CharField(max_length=64, blank=True)
    numero_certificado_fornecedor_componente_snapshot = models.CharField(max_length=64, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    composicao_json = models.JSONField(default=dict, blank=True)
    ensaio_tracao_json = models.JSONField(default=dict, blank=True)
    ensaio_impacto_json = models.JSONField(default=dict, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordem', 'id']


class CertificadoFornecedorEntrada(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'rascunho', 'Rascunho'
        REGISTRADO = 'registrado', 'Registrado'
        CANCELADO = 'cancelado', 'Cancelado'

    numero_certificado_fornecedor = models.CharField(max_length=64, blank=True)
    fornecedor = models.ForeignKey(
        'cadastros.Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_fornecedor_entrada',
    )
    fornecedor_nome_snapshot = models.CharField(max_length=255, blank=True)
    fornecedor_cnpj_snapshot = models.CharField(max_length=32, blank=True)
    nf_entrada_historica = models.ForeignKey(
        'fiscal.NFeEntradaHistoricaImportada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_fornecedor',
    )
    nf_entrada_operacional = models.ForeignKey(
        'fiscal.NFeEntrada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_fornecedor',
    )
    numero_nf_entrada = models.CharField(max_length=64, blank=True)
    serie_nf_entrada = models.CharField(max_length=16, blank=True)
    data_nf_entrada = models.DateField(null=True, blank=True)
    empresa_destinataria = models.ForeignKey(
        'cadastros.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificados_fornecedor_recebidos',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RASCUNHO)
    observacoes = models.TextField(blank=True)
    arquivo_original = models.FileField(upload_to='certificados_fornecedor/%Y/%m/', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']


class ItemCertificadoFornecedorEntrada(models.Model):
    class TipoDadosTecnicos(models.TextChoices):
        PADRAO_ITEM = 'PADRAO_ITEM', 'Dados por item'
        VALVULA_COMPONENTES = 'VALVULA_COMPONENTES', 'Dados por componentes de válvula'

    certificado_fornecedor = models.ForeignKey(
        CertificadoFornecedorEntrada,
        on_delete=models.CASCADE,
        related_name='itens',
    )
    ordem = models.PositiveIntegerField(default=1)
    produto = models.ForeignKey(
        'produtos.Produto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_certificado_fornecedor_entrada',
    )
    codigo_produto = models.CharField(max_length=128, blank=True)
    descricao_material = models.CharField(max_length=512, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    unidade = models.CharField(max_length=16, blank=True)
    ncm = models.CharField(max_length=16, blank=True)
    norma = models.CharField(max_length=128, blank=True)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    numero_certificado_fornecedor_item = models.CharField(max_length=64, blank=True)
    data_certificado_fornecedor_item = models.DateField(null=True, blank=True)
    pagina_certificado_fornecedor = models.CharField(max_length=32, blank=True)
    observacao_origem_certificado = models.TextField(blank=True)
    tipo_dados_tecnicos = models.CharField(
        max_length=32,
        choices=TipoDadosTecnicos.choices,
        default=TipoDadosTecnicos.PADRAO_ITEM,
    )
    composicao_json = models.JSONField(default=dict, blank=True)
    ensaio_tracao_json = models.JSONField(default=dict, blank=True)
    ensaio_impacto_json = models.JSONField(default=dict, blank=True)
    observacoes_item = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    item_conferencia = models.ForeignKey(
        'fiscal.ItemNFeEntradaConferencia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_certificado_fornecedor',
    )
    origem_nfe_item_numero = models.PositiveSmallIntegerField(null=True, blank=True)
    origem_vinculada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['item_conferencia'],
                condition=models.Q(item_conferencia__isnull=False, ativo=True),
                name='uniq_item_cf_item_conferencia_ativo',
            ),
        ]


class ComponenteCertificadoFornecedorEntrada(models.Model):
    item_certificado_fornecedor = models.ForeignKey(
        ItemCertificadoFornecedorEntrada,
        on_delete=models.CASCADE,
        related_name='componentes',
    )
    ordem = models.PositiveIntegerField(default=1)
    nome_componente = models.CharField(max_length=120)
    descricao_componente = models.CharField(max_length=255, blank=True)
    norma = models.CharField(max_length=128, blank=True)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    revisao_corrida = models.CharField(max_length=64, blank=True)
    numero_certificado_fornecedor_componente = models.CharField(max_length=64, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    composicao_json = models.JSONField(default=dict, blank=True)
    ensaio_tracao_json = models.JSONField(default=dict, blank=True)
    ensaio_impacto_json = models.JSONField(default=dict, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordem', 'id']


class SequenciaCertificadoQualidade(models.Model):
    """Sequência diária CQ-AAAAMMDD-NNNN."""

    data_referencia = models.DateField(db_index=True, unique=True)
    proximo_numero = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Sequência certificado de qualidade'
        verbose_name_plural = 'Sequências certificado de qualidade'
        ordering = ['-data_referencia']

    def __str__(self):
        return f'CQ {self.data_referencia} → próximo {self.proximo_numero}'
