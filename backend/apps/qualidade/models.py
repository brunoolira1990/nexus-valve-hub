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
        SUBSTITUIDO = 'substituido', 'Substituído'

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
    rastreabilidade_status_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            'Snapshot do status de rastreabilidade no momento da emissão. '
            'Usado para congelar a avaliação em CQs emitidos.'
        ),
    )
    substituido_por = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='substitui',
        help_text='Versão mais recente que substituiu este CQ (reemissão).',
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



    def reemitir(self):
        """Cria um novo CQ clonando este (itens + componentes + corridas), incrementa serie,
        e marca este como SUBSTITUIDO apontando para o novo.

        Retorna o novo CertificadoQualidade (status RASCUNHO).
        """
        from django.db import transaction
        from apps.qualidade.services.numeracao_certificado_qualidade import (
            proxima_serie,
            gerar_numero_certificado_qualidade,
        )
        from apps.qualidade.models import (
            ItemCertificadoQualidade,
            ItemCertificadoQualidadeComponente,
            ItemCertificadoQualidadeCorrida,
        )
        
        with transaction.atomic():
            novo = CertificadoQualidade.objects.create(
                numero=gerar_numero_certificado_qualidade(),
                serie=proxima_serie(self.serie),
                cliente=self.cliente,
                cliente_nome_snapshot=self.cliente_nome_snapshot,
                cliente_cnpj_snapshot=self.cliente_cnpj_snapshot,
                pedido_cliente=self.pedido_cliente,
                nota_fiscal_numero=self.nota_fiscal_numero,
                nota_fiscal=self.nota_fiscal,
                nota_fiscal_historica=self.nota_fiscal_historica,
                data_emissao=self.data_emissao,
                observacoes=self.observacoes,
                texto_padrao=self.texto_padrao,
                status=CertificadoQualidade.Status.RASCUNHO,
                tipo_certificado=self.tipo_certificado,
            )
            
            for item_orig in self.itens.all():
                item_novo = ItemCertificadoQualidade.objects.create(
                    certificado=novo,
                    ordem=item_orig.ordem,
                    tipo_dados_tecnicos=item_orig.tipo_dados_tecnicos,
                    produto=item_orig.produto,
                    codigo_produto=item_orig.codigo_produto,
                    descricao_material=item_orig.descricao_material,
                    quantidade=item_orig.quantidade,
                    unidade=item_orig.unidade,
                    norma=item_orig.norma,
                    corrida=item_orig.corrida,
                    lote=item_orig.lote,
                    ncm=item_orig.ncm,
                    status_vinculo_produto=item_orig.status_vinculo_produto,
                    produto_snapshot=item_orig.produto_snapshot,
                    produto_codigo=item_orig.produto_codigo,
                    produto_descricao=item_orig.produto_descricao,
                    produto_ncm_efetivo=item_orig.produto_ncm_efetivo,
                    origem_rastreabilidade_tipo=item_orig.origem_rastreabilidade_tipo,
                    origem_status_tecnico=item_orig.origem_status_tecnico,
                    origem_observacoes=item_orig.origem_observacoes,
                    observacoes_item=item_orig.observacoes_item,
                    composicao_json=dict(item_orig.composicao_json or {}),
                    ensaio_tracao_json=dict(item_orig.ensaio_tracao_json or {}),
                    ensaio_impacto_json=dict(item_orig.ensaio_impacto_json or {}),
                    certificado_fornecedor_origem_id=item_orig.certificado_fornecedor_origem_id,
                    item_certificado_fornecedor_origem_id=item_orig.item_certificado_fornecedor_origem_id,
                    fornecedor_nome_snapshot=item_orig.fornecedor_nome_snapshot,
                    nf_entrada_snapshot=item_orig.nf_entrada_snapshot,
                    codigo_item_fornecedor_snapshot=item_orig.codigo_item_fornecedor_snapshot,
                    descricao_item_fornecedor_snapshot=item_orig.descricao_item_fornecedor_snapshot,
                    numero_certificado_fornecedor_item_snapshot=item_orig.numero_certificado_fornecedor_item_snapshot,
                    corrida_snapshot=item_orig.corrida_snapshot,
                    lote_snapshot=item_orig.lote_snapshot,
                    incluir_no_certificado=item_orig.incluir_no_certificado,
                    motivo_nao_inclusao=item_orig.motivo_nao_inclusao,
                    observacao_nao_inclusao=item_orig.observacao_nao_inclusao,
                )
                
                for comp_orig in item_orig.componentes.all():
                    ItemCertificadoQualidadeComponente.objects.create(
                        item=item_novo,
                        ordem=comp_orig.ordem,
                        nome_componente=comp_orig.nome_componente,
                        descricao_componente=comp_orig.descricao_componente,
                        norma=comp_orig.norma,
                        corrida=comp_orig.corrida,
                        lote=comp_orig.lote,
                        revisao_corrida=comp_orig.revisao_corrida,
                        numero_certificado_fornecedor_componente=comp_orig.numero_certificado_fornecedor_componente,
                        quantidade=comp_orig.quantidade,
                        composicao_json=dict(comp_orig.composicao_json or {}),
                        ensaio_tracao_json=dict(comp_orig.ensaio_tracao_json or {}),
                        ensaio_impacto_json=dict(comp_orig.ensaio_impacto_json or {}),
                        observacoes=comp_orig.observacoes,
                        ativo=comp_orig.ativo,
                    )
                
                for corr_orig in item_orig.corridas_adicionais.all():
                    ItemCertificadoQualidadeCorrida.objects.create(
                        item=item_novo,
                        corrida=corr_orig.corrida,
                        lote=corr_orig.lote,
                        quantidade=corr_orig.quantidade,
                    )
            
            self.substituido_por = novo
            self.status = CertificadoQualidade.Status.SUBSTITUIDO
            self.save(update_fields=['substituido_por', 'status'])
        
        return novo

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


class ItemCertificadoFornecedorCorrida(models.Model):
    item_certificado = models.ForeignKey(
        ItemCertificadoFornecedorEntrada,
        on_delete=models.CASCADE,
        related_name='corridas_adicionais',
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    composicao_json = models.JSONField(default=dict, blank=True)
    ensaio_tracao_json = models.JSONField(default=dict, blank=True)
    ensaio_impacto_json = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

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


class ItemCertificadoQualidadeCorrida(models.Model):
    """Corridas adicionais por item de certificado de qualidade (A1 feature)."""

    item_certificado = models.ForeignKey(
        ItemCertificadoQualidade,
        on_delete=models.CASCADE,
        related_name='corridas_adicionais',
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    corrida = models.CharField(max_length=64, blank=True)
    lote = models.CharField(max_length=64, blank=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    composicao_json = models.JSONField(default=dict, blank=True)
    ensaio_tracao_json = models.JSONField(default=dict, blank=True)
    ensaio_impacto_json = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'id']
