from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

from .utils import validar_cnpj_django


def _default_dias_parcelas():
    return []


def _norm_cnpj(val: str) -> str:
    if val is None:
        return ''
    return ''.join(c for c in str(val) if c.isdigit())


class Empresa(models.Model):
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


class CondicaoPagamento(models.Model):
    descricao = models.CharField(max_length=100, unique=True)
    dias_parcelas = ArrayField(
        models.IntegerField(),
        default=_default_dias_parcelas,
        blank=True,
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['descricao']

    def __str__(self):
        return f"{self.descricao} ({', '.join(str(d) for d in self.dias_parcelas)} dias)"


class Cliente(models.Model):
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
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    condicao_pagamento_padrao = models.ForeignKey(
        CondicaoPagamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes_condicao_padrao',
    )
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

    class Meta:
        ordering = ['razao_social']

    def __str__(self):
        return self.razao_social

    def clean(self):
        super().clean()
        if self.cnpj and _norm_cnpj(self.cnpj) == '':
            raise ValidationError({'cnpj': 'Informe um CNPJ válido ou deixe em branco.'})


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
    condicao_pagamento_padrao = models.ForeignKey(
        CondicaoPagamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fornecedores_condicao_padrao',
    )
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


class Transportadora(models.Model):
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=20, unique=True)
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
