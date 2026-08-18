from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

from .utils import normalizar_cnpj, validar_cnpj_django


def _default_dias_parcelas():
    return []


def _norm_cnpj(val: str) -> str:
    return normalizar_cnpj(val)


class Empresa(models.Model):
    class NfeAmbiente(models.TextChoices):
        HOMOLOGACAO = 'homologacao', 'Homologação'
        PRODUCAO = 'producao', 'Produção'

    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=20, unique=True, validators=[validar_cnpj_django])
    ie = models.CharField(max_length=32, blank=True)
    im = models.CharField(max_length=32, blank=True)
    regime_tributario = models.CharField(max_length=64, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=32, blank=True)
    complemento = models.CharField(max_length=128, blank=True)
    bairro = models.CharField(max_length=128, blank=True)
    cidade = models.CharField(max_length=128, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=16, blank=True)
    telefone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    site = models.CharField(max_length=255, blank=True)
    empresa_pai = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='filiais',
    )
    certificado_arquivo = models.FileField(upload_to='certificados/', null=True, blank=True)
    senha_certificado = models.CharField(max_length=128, blank=True)
    certificado_validade = models.DateField(null=True, blank=True)
    logotipo = models.ImageField(upload_to='logos/', null=True, blank=True)
    nfe_ambiente = models.CharField(
        max_length=16,
        choices=NfeAmbiente.choices,
        default=NfeAmbiente.HOMOLOGACAO,
        help_text='Ambiente fiscal NF-e desejado para emissão desta empresa.',
    )
    criado_em = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['razao_social']

    def __str__(self):
        return self.razao_social

    def clean(self):
        super().clean()
        if self.cnpj and _norm_cnpj(self.cnpj) == '':
            raise ValidationError({'cnpj': 'Informe um CNPJ válido ou deixe em branco.'})

    def save(self, *args, **kwargs):
        self.cnpj = normalizar_cnpj(self.cnpj)
        if self.certificado_arquivo and self.senha_certificado:
            self._validar_certificado()
        super().save(*args, **kwargs)

    def _validar_certificado(self):
        from cryptography.hazmat.primitives.serialization import pkcs12

        try:
            self.certificado_arquivo.seek(0)
            p12_data = self.certificado_arquivo.read()
            if not p12_data:
                raise ValidationError({'certificado_arquivo': 'Arquivo de certificado vazio.'})

            _private_key, certificate, _additional = pkcs12.load_key_and_certificates(
                p12_data,
                self.senha_certificado.encode('utf-8'),
            )
            if certificate is not None:
                na = getattr(certificate, 'not_valid_after_utc', None) or getattr(
                    certificate, 'not_valid_after', None
                )
                if na is not None:
                    self.certificado_validade = na.date() if hasattr(na, 'date') else na
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError({'senha_certificado': f'Falha ao validar certificado: {str(e)}'}) from e


class Cliente(models.Model):
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=20, unique=True, validators=[validar_cnpj_django])
    ie = models.CharField(max_length=32, blank=True)
    ie_isento = models.BooleanField(
        default=False,
        help_text='Cliente isento de Inscrição Estadual (indIEDest=2 na NF-e).',
    )
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=32, blank=True)
    complemento = models.CharField(max_length=128, blank=True)
    bairro = models.CharField(max_length=128, blank=True)
    cidade = models.CharField(max_length=128, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=16, blank=True)
    telefone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    contato_responsavel = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    inscricao_municipal = models.CharField(max_length=20, blank=True)
    suframa = models.CharField(max_length=20, blank=True)
    email_nf = models.EmailField(blank=True)
    telefone_alternativo = models.CharField(max_length=20, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    transportadora_padrao = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes_transportadora_padrao',
    )
    vendedor_padrao = models.CharField(max_length=100, blank=True)
    bloqueado = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    ddd = models.CharField(max_length=4, blank=True)
    banco = models.CharField(max_length=100, blank=True)
    agencia = models.CharField(max_length=20, blank=True)
    conta = models.CharField(max_length=32, blank=True)
    tipo_conta = models.CharField(max_length=20, blank=True)
    cnae = models.CharField(max_length=20, blank=True)
    regime_tributario = models.CharField(max_length=64, blank=True)
    integracao_texto = models.TextField(blank=True)
    informacoes_complementares_nfe = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Informações recorrentes deste cliente para Dados Adicionais da NF-e/DANFE '
            '(endereço de entrega, horário de recebimento, instruções externas).'
        ),
    )

    class Meta:
        ordering = ['razao_social']

    def __str__(self):
        return self.razao_social

    def clean(self):
        super().clean()
        if self.cnpj and _norm_cnpj(self.cnpj) == '':
            raise ValidationError({'cnpj': 'Informe um CNPJ válido ou deixe em branco.'})

    def save(self, *args, **kwargs):
        self.cnpj = normalizar_cnpj(self.cnpj)
        super().save(*args, **kwargs)


class EnderecoEntregaCliente(models.Model):
    """
    Endereços de entrega do cliente.

    O endereço fiscal permanece nos campos embutidos de Cliente (logradouro, cep, etc.),
    usados pelo <dest> da NF-e e por endereco_fiscal — sem migração de dados existentes.
    """

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='enderecos_entrega',
    )
    identificacao = models.CharField(
        max_length=120,
        blank=True,
        help_text='Apelido para diferenciar endereços (ex.: Filial Campinas).',
    )
    cep = models.CharField(max_length=16, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=32, blank=True)
    complemento = models.CharField(max_length=128, blank=True)
    bairro = models.CharField(max_length=128, blank=True)
    cidade = models.CharField(max_length=128, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    principal = models.BooleanField(
        default=False,
        help_text='Endereço de entrega padrão quando houver mais de um.',
    )

    class Meta:
        ordering = ['-principal', 'id']
        verbose_name = 'Endereço de entrega do cliente'
        verbose_name_plural = 'Endereços de entrega do cliente'

    def __str__(self):
        rotulo = (self.identificacao or self.logradouro or '').strip()
        return rotulo or f'Entrega #{self.pk}'


class ContatoCliente(models.Model):
    class Tipo(models.TextChoices):
        COMERCIAL = 'COMERCIAL', 'Comercial'
        FINANCEIRO = 'FINANCEIRO', 'Financeiro'
        TECNICO = 'TECNICO', 'Técnico'
        OUTRO = 'OUTRO', 'Outro'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='contatos',
    )
    tipo = models.CharField(max_length=16, choices=Tipo.choices, default=Tipo.COMERCIAL)
    nome = models.CharField(max_length=255, blank=True)
    telefone = models.CharField(max_length=32, blank=True)
    celular = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    principal = models.BooleanField(
        default=False,
        help_text='Contato principal dentro do mesmo tipo.',
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Contato inativo permanece cadastrado, mas não é elegível para envio fiscal.',
    )
    recebe_documentos_fiscais = models.BooleanField(
        default=False,
        help_text='Indica que o e-mail deste contato pode receber documentos fiscais (DANFE/XML).',
    )

    class Meta:
        ordering = ['tipo', '-principal', 'id']
        verbose_name = 'Contato do cliente'
        verbose_name_plural = 'Contatos do cliente'

    def __str__(self):
        nome = (self.nome or '').strip()
        return nome or f'{self.get_tipo_display()} #{self.pk}'


class Fornecedor(models.Model):
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=20, unique=True, validators=[validar_cnpj_django])
    ie = models.CharField(max_length=32, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=32, blank=True)
    complemento = models.CharField(max_length=128, blank=True)
    bairro = models.CharField(max_length=128, blank=True)
    cidade = models.CharField(max_length=128, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=16, blank=True)
    telefone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    contato_responsavel = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    inscricao_municipal = models.CharField(max_length=20, blank=True)
    suframa = models.CharField(max_length=20, blank=True)
    email_nf = models.EmailField(blank=True)
    telefone_alternativo = models.CharField(max_length=20, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    condicao_pagamento_texto = models.CharField(max_length=120, blank=True)
    dias_parcelas = ArrayField(models.IntegerField(), default=_default_dias_parcelas, blank=True)
    quantidade_parcelas = models.PositiveSmallIntegerField(default=0)
    transportadora_padrao = models.ForeignKey(
        'cadastros.Transportadora',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fornecedores_transportadora_padrao',
    )
    prazo_entrega = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    ddd = models.CharField(max_length=4, blank=True)
    banco = models.CharField(max_length=100, blank=True)
    agencia = models.CharField(max_length=20, blank=True)
    conta = models.CharField(max_length=32, blank=True)
    tipo_conta = models.CharField(max_length=20, blank=True)
    cnae = models.CharField(max_length=20, blank=True)
    regime_tributario = models.CharField(max_length=64, blank=True)
    integracao_texto = models.TextField(blank=True)

    class Meta:
        ordering = ['razao_social']

    def __str__(self):
        return self.razao_social

    def clean(self):
        super().clean()
        if self.cnpj and _norm_cnpj(self.cnpj) == '':
            raise ValidationError({'cnpj': 'Informe um CNPJ válido ou deixe em branco.'})

    def save(self, *args, **kwargs):
        self.cnpj = normalizar_cnpj(self.cnpj)
        super().save(*args, **kwargs)


class Colaborador(models.Model):
    """Pessoa interna do ERP (vendedor, comprador, responsáveis por área)."""

    nome = models.CharField(max_length=255)
    codigo = models.CharField(max_length=32, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=32, blank=True)
    ativo = models.BooleanField(default=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colaborador_vinculado',
    )
    eh_vendedor = models.BooleanField(default=False)
    eh_comprador = models.BooleanField(default=False)
    eh_responsavel_fiscal = models.BooleanField(default=False)
    eh_responsavel_financeiro = models.BooleanField(default=False)
    eh_responsavel_estoque = models.BooleanField(default=False)
    eh_responsavel_qualidade = models.BooleanField(default=False)
    eh_administrador = models.BooleanField(default=False)
    cargo = models.CharField(max_length=120, blank=True)
    departamento = models.CharField(max_length=120, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Colaborador'
        verbose_name_plural = 'Colaboradores'

    def __str__(self):
        return self.nome or self.codigo or str(self.pk)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from apps.cadastros.colaborador_sync import sincronizar_vendedor_colaborador

        sincronizar_vendedor_colaborador(self)


class Transportadora(models.Model):
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=20, unique=True, validators=[validar_cnpj_django])
    ie = models.CharField(max_length=32, blank=True)
    inscricao_municipal = models.CharField(max_length=20, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=32, blank=True)
    complemento = models.CharField(max_length=128, blank=True)
    bairro = models.CharField(max_length=128, blank=True)
    cidade = models.CharField(max_length=128, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=16, blank=True)
    telefone = models.CharField(max_length=64, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    contato = models.CharField(max_length=100, blank=True)
    placa_padrao = models.CharField(max_length=16, blank=True)
    uf_placa = models.CharField(max_length=2, blank=True)
    valor_km = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    ddd = models.CharField(max_length=4, blank=True)
    suframa = models.CharField(max_length=20, blank=True)
    email_nf = models.EmailField(blank=True)
    banco = models.CharField(max_length=100, blank=True)
    agencia = models.CharField(max_length=20, blank=True)
    conta = models.CharField(max_length=32, blank=True)
    tipo_conta = models.CharField(max_length=20, blank=True)
    cnae = models.CharField(max_length=20, blank=True)
    regime_tributario = models.CharField(max_length=64, blank=True)
    integracao_texto = models.TextField(blank=True)

    class Meta:
        ordering = ['razao_social']

    def __str__(self):
        return self.razao_social

    def clean(self):
        super().clean()
        if self.cnpj and _norm_cnpj(self.cnpj) == '':
            raise ValidationError({'cnpj': 'Informe um CNPJ válido ou deixe em branco.'})

    def save(self, *args, **kwargs):
        self.cnpj = normalizar_cnpj(self.cnpj)
        super().save(*args, **kwargs)
