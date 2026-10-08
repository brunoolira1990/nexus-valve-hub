"""Serializers API financeiro operacional."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.financeiro.constants import (
    FormaPagamentoCodigo,
    TipoMovimentoFinanceiro,
    label_forma_pagamento,
    label_tipo_movimento,
)
from apps.financeiro.operacional import (
    credito_operational_flags,
    titulo_exclusao_flags,
)
from apps.financeiro.status import CENTAVO
from apps.financeiro.models import (
    BaixaFinanceira,
    CategoriaFinanceira,
    CentroCusto,
    ContaFinanceira,
    CreditoFinanceiro,
    CreditoFinanceiroEvento,
    FinanceiroEvento,
    ParcelaFinanceira,
    TituloFinanceiro,
)

STATUS_LABELS = {
    TituloFinanceiro.Status.EM_ABERTO: 'Em aberto',
    TituloFinanceiro.Status.VENCIDO: 'Vencido',
    TituloFinanceiro.Status.PARCIALMENTE_RECEBIDO: 'Parcialmente recebido',
    TituloFinanceiro.Status.RECEBIDO: 'Recebido',
    TituloFinanceiro.Status.PARCIALMENTE_PAGO: 'Parcialmente pago',
    TituloFinanceiro.Status.PAGO: 'Pago',
    TituloFinanceiro.Status.CANCELADO: 'Cancelado',
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status.replace('_', ' ').title())


def _titulo_origem_exibicao(obj: TituloFinanceiro) -> str:
    if obj.origem_tipo == TituloFinanceiro.OrigemTipo.NFE_SAIDA:
        num = (obj.origem_numero or '').strip()
        if num:
            return f'NF-e nº {num}'
        return 'NF-e Saída'
    if obj.origem_tipo == TituloFinanceiro.OrigemTipo.FATURAMENTO:
        num = (obj.origem_numero or '').strip()
        if num:
            return f'Faturamento {num}'
        return 'Faturamento'
    if obj.origem_tipo == TituloFinanceiro.OrigemTipo.NFE_ENTRADA:
        num = (obj.origem_numero or '').strip()
        if num:
            return f'NF-e Entrada nº {num}'
        return 'NF-e Entrada'
    partes = []
    if (obj.origem_descricao or '').strip():
        partes.append(obj.origem_descricao.strip())
    if (obj.origem_numero or '').strip():
        partes.append(obj.origem_numero.strip())
    if not partes and obj.origem_tipo:
        partes.append(obj.get_origem_tipo_display())
    return ' · '.join(partes) if partes else 'Manual'


def titulo_operational_flags(obj: TituloFinanceiro) -> dict[str, bool]:
    baixas_ativas = obj.baixas.filter(estornada=False)
    possui_baixa_ativa = baixas_ativas.exists()
    valor_aberto = obj.valor_aberto or Decimal('0')
    valor_baixado = obj.valor_baixado or Decimal('0')
    cancelado = bool(obj.cancelado)
    pode_baixar = not cancelado and valor_aberto > CENTAVO
    pode_editar = not cancelado and valor_baixado <= CENTAVO
    pode_cancelar = not cancelado and valor_baixado <= CENTAVO
    pode_estornar_baixa = possui_baixa_ativa and not cancelado
    pode_abater = pode_baixar
    pode_aplicar_credito = pode_baixar
    possui_credito_aplicado = baixas_ativas.filter(
        tipo_movimento=TipoMovimentoFinanceiro.USO_CREDITO,
    ).exists()
    possui_abatimento = baixas_ativas.filter(
        tipo_movimento__in=(
            TipoMovimentoFinanceiro.ABATIMENTO,
            TipoMovimentoFinanceiro.ABATIMENTO_DEVOLUCAO,
        ),
    ).exists()
    exclusao = titulo_exclusao_flags(obj)
    return {
        'pode_editar': pode_editar,
        'pode_baixar': pode_baixar,
        'pode_cancelar': pode_cancelar,
        'possui_baixa_ativa': possui_baixa_ativa,
        'pode_estornar_baixa': pode_estornar_baixa,
        'pode_abater': pode_abater,
        'pode_aplicar_credito': pode_aplicar_credito,
        'possui_credito_aplicado': possui_credito_aplicado,
        'possui_abatimento': possui_abatimento,
        **exclusao,
    }


class ContaFinanceiraSerializer(serializers.ModelSerializer):
    tipo_label = serializers.SerializerMethodField()

    class Meta:
        model = ContaFinanceira
        fields = '__all__'

    def get_tipo_label(self, obj) -> str:
        return obj.get_tipo_display()

    def validate(self, attrs):
        tipo = attrs.get('tipo', getattr(self.instance, 'tipo', None))
        banco = attrs.get('banco', getattr(self.instance, 'banco', '') if self.instance else '')
        if tipo == ContaFinanceira.Tipo.BANCO and not (banco or '').strip():
            raise serializers.ValidationError(
                {'banco': 'Informe o banco para contas do tipo Banco.'},
            )
        return attrs


class CategoriaFinanceiraSerializer(serializers.ModelSerializer):
    tipo_label = serializers.SerializerMethodField()

    class Meta:
        model = CategoriaFinanceira
        fields = '__all__'

    def get_tipo_label(self, obj) -> str:
        return obj.get_tipo_display()


class CentroCustoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CentroCusto
        fields = '__all__'


class FinanceiroEventoSerializer(serializers.ModelSerializer):
    acao_label = serializers.SerializerMethodField()
    usuario_nome = serializers.SerializerMethodField()

    class Meta:
        model = FinanceiroEvento
        fields = '__all__'

    def get_acao_label(self, obj) -> str:
        return obj.get_acao_display()

    def get_usuario_nome(self, obj) -> str:
        if not obj.usuario_id:
            return ''
        u = obj.usuario
        return (u.get_full_name() or u.username or '').strip()


class CreditoFinanceiroEventoSerializer(serializers.ModelSerializer):
    acao_label = serializers.SerializerMethodField()
    usuario_nome = serializers.SerializerMethodField()

    class Meta:
        model = CreditoFinanceiroEvento
        fields = '__all__'

    def get_acao_label(self, obj) -> str:
        return obj.get_acao_display()

    def get_usuario_nome(self, obj) -> str:
        if not obj.usuario_id:
            return ''
        u = obj.usuario
        return (u.get_full_name() or u.username or '').strip()


class BaixaFinanceiraSerializer(serializers.ModelSerializer):
    forma_pagamento_label = serializers.SerializerMethodField()
    forma_pagamento_nome = serializers.SerializerMethodField()
    tipo_movimento_label = serializers.SerializerMethodField()
    conta_financeira_nome = serializers.SerializerMethodField()
    pode_estornar = serializers.SerializerMethodField()

    class Meta:
        model = BaixaFinanceira
        fields = '__all__'

    def get_forma_pagamento_label(self, obj) -> str:
        return label_forma_pagamento(obj.forma_pagamento_codigo)

    def get_forma_pagamento_nome(self, obj) -> str:
        return label_forma_pagamento(obj.forma_pagamento_codigo)

    def get_tipo_movimento_label(self, obj) -> str:
        return label_tipo_movimento(obj.tipo_movimento)

    def get_conta_financeira_nome(self, obj) -> str:
        if not obj.conta_financeira_id:
            return ''
        return (obj.conta_financeira.nome or '').strip()

    def get_pode_estornar(self, obj) -> bool:
        return not obj.estornada


class ParcelaFinanceiraSerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = ParcelaFinanceira
        fields = '__all__'

    def get_status_label(self, obj) -> str:
        return status_label(obj.status)


class TituloFinanceiroSerializer(serializers.ModelSerializer):
    forma_pagamento_prevista_label = serializers.SerializerMethodField()
    cliente_nome = serializers.SerializerMethodField()
    cliente_cnpj = serializers.SerializerMethodField()
    fornecedor_nome = serializers.SerializerMethodField()
    fornecedor_cnpj = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    tipo_lancamento_label = serializers.SerializerMethodField()
    origem_exibicao = serializers.SerializerMethodField()
    origem_nfe_detalhe = serializers.SerializerMethodField()
    origem_nfe_entrada_detalhe = serializers.SerializerMethodField()
    alerta_origem_cancelada = serializers.SerializerMethodField()
    categoria_nome = serializers.SerializerMethodField()
    pode_editar = serializers.SerializerMethodField()
    pode_baixar = serializers.SerializerMethodField()
    pode_cancelar = serializers.SerializerMethodField()
    possui_baixa_ativa = serializers.SerializerMethodField()
    pode_estornar_baixa = serializers.SerializerMethodField()
    pode_abater = serializers.SerializerMethodField()
    pode_aplicar_credito = serializers.SerializerMethodField()
    possui_credito_aplicado = serializers.SerializerMethodField()
    possui_abatimento = serializers.SerializerMethodField()
    pode_excluir = serializers.SerializerMethodField()
    origem_manual = serializers.SerializerMethodField()
    possui_movimento_financeiro = serializers.SerializerMethodField()
    possui_movimento_financeiro_ativo = serializers.SerializerMethodField()
    possui_apenas_movimentos_estornados = serializers.SerializerMethodField()
    possui_vinculo_origem = serializers.SerializerMethodField()
    motivo_bloqueio_exclusao = serializers.SerializerMethodField()
    saldo_integral_reaberto = serializers.SerializerMethodField()
    valor_movimentado_ativo_zero = serializers.SerializerMethodField()
    parcelas = ParcelaFinanceiraSerializer(many=True, read_only=True)
    baixas = BaixaFinanceiraSerializer(many=True, read_only=True)
    eventos = FinanceiroEventoSerializer(many=True, read_only=True)

    class Meta:
        model = TituloFinanceiro
        fields = '__all__'

    def _flags(self, obj: TituloFinanceiro) -> dict[str, bool]:
        cached = getattr(obj, '_operational_flags_cache', None)
        if cached is None:
            cached = titulo_operational_flags(obj)
            obj._operational_flags_cache = cached
        return cached

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get('detail'):
            data.pop('parcelas', None)
            data.pop('baixas', None)
            data.pop('eventos', None)
        return data

    def get_origem_exibicao(self, obj) -> str:
        return _titulo_origem_exibicao(obj)

    def get_origem_nfe_detalhe(self, obj) -> dict | None:
        from apps.fiscal.nfe_saida_financeiro import montar_origem_nfe_detalhe

        return montar_origem_nfe_detalhe(obj)

    def get_origem_nfe_entrada_detalhe(self, obj) -> dict | None:
        from apps.fiscal.nfe_entrada_financeiro import montar_origem_nfe_entrada_detalhe

        return montar_origem_nfe_entrada_detalhe(obj)

    def get_alerta_origem_cancelada(self, obj) -> str:
        from apps.fiscal.nfe_entrada_financeiro import (
            MSG_ALERTA_NFE_CANCELADA as MSG_ENTRADA,
            titulo_origem_nfe_entrada_cancelada,
        )
        from apps.fiscal.nfe_saida_financeiro import MSG_ALERTA_NFE_CANCELADA as MSG_SAIDA, titulo_origem_nfe_cancelada

        if titulo_origem_nfe_cancelada(obj):
            return MSG_SAIDA
        if titulo_origem_nfe_entrada_cancelada(obj):
            return MSG_ENTRADA
        return ''

    def get_categoria_nome(self, obj) -> str:
        if not obj.categoria_id:
            return ''
        return (obj.categoria.nome or '').strip()

    def get_pode_editar(self, obj) -> bool:
        return self._flags(obj)['pode_editar']

    def get_pode_baixar(self, obj) -> bool:
        return self._flags(obj)['pode_baixar']

    def get_pode_cancelar(self, obj) -> bool:
        return self._flags(obj)['pode_cancelar']

    def get_possui_baixa_ativa(self, obj) -> bool:
        return self._flags(obj)['possui_baixa_ativa']

    def get_pode_estornar_baixa(self, obj) -> bool:
        return self._flags(obj)['pode_estornar_baixa']

    def get_pode_abater(self, obj) -> bool:
        return self._flags(obj)['pode_abater']

    def get_pode_aplicar_credito(self, obj) -> bool:
        return self._flags(obj)['pode_aplicar_credito']

    def get_possui_credito_aplicado(self, obj) -> bool:
        return self._flags(obj)['possui_credito_aplicado']

    def get_possui_abatimento(self, obj) -> bool:
        return self._flags(obj)['possui_abatimento']

    def get_pode_excluir(self, obj) -> bool:
        return self._flags(obj)['pode_excluir']

    def get_origem_manual(self, obj) -> bool:
        return self._flags(obj)['origem_manual']

    def get_possui_movimento_financeiro(self, obj) -> bool:
        return self._flags(obj)['possui_movimento_financeiro']

    def get_possui_vinculo_origem(self, obj) -> bool:
        return self._flags(obj)['possui_vinculo_origem']

    def get_possui_movimento_financeiro_ativo(self, obj) -> bool:
        return self._flags(obj)['possui_movimento_financeiro_ativo']

    def get_possui_apenas_movimentos_estornados(self, obj) -> bool:
        return self._flags(obj)['possui_apenas_movimentos_estornados']

    def get_motivo_bloqueio_exclusao(self, obj) -> str:
        return self._flags(obj)['motivo_bloqueio_exclusao']

    def get_saldo_integral_reaberto(self, obj) -> bool:
        return self._flags(obj)['saldo_integral_reaberto']

    def get_valor_movimentado_ativo_zero(self, obj) -> bool:
        return self._flags(obj)['valor_movimentado_ativo_zero']

    def get_forma_pagamento_prevista_label(self, obj) -> str:
        if not obj.forma_pagamento_prevista_codigo:
            return ''
        return label_forma_pagamento(obj.forma_pagamento_prevista_codigo)

    def get_cliente_nome(self, obj) -> str:
        if not obj.cliente_id:
            return ''
        c = obj.cliente
        return (c.razao_social or c.nome_fantasia or '').strip()

    def get_cliente_cnpj(self, obj) -> str:
        if not obj.cliente_id:
            return ''
        return (obj.cliente.cnpj or '').strip()

    def get_fornecedor_nome(self, obj) -> str:
        if not obj.fornecedor_id:
            return ''
        f = obj.fornecedor
        return (f.razao_social or f.nome_fantasia or '').strip()

    def get_fornecedor_cnpj(self, obj) -> str:
        if not obj.fornecedor_id:
            return ''
        return (obj.fornecedor.cnpj or '').strip()

    def get_status_label(self, obj) -> str:
        return status_label(obj.status)

    def get_tipo_lancamento_label(self, obj) -> str:
        if not obj.tipo_lancamento:
            return ''
        return obj.get_tipo_lancamento_display()


CREDITO_STATUS_LABELS = {
    CreditoFinanceiro.Status.DISPONIVEL: 'Disponível',
    CreditoFinanceiro.Status.PARCIALMENTE_UTILIZADO: 'Parcialmente utilizado',
    CreditoFinanceiro.Status.UTILIZADO: 'Utilizado',
    CreditoFinanceiro.Status.CANCELADO: 'Cancelado',
}


def credito_status_label(status: str) -> str:
    return CREDITO_STATUS_LABELS.get(status, status.replace('_', ' ').title())


class CreditoFinanceiroSerializer(serializers.ModelSerializer):
    eventos = CreditoFinanceiroEventoSerializer(many=True, read_only=True)
    status_label = serializers.SerializerMethodField()
    tipo_label = serializers.SerializerMethodField()
    origem_tipo_label = serializers.SerializerMethodField()
    cliente_nome = serializers.SerializerMethodField()
    cliente_cnpj = serializers.SerializerMethodField()
    fornecedor_nome = serializers.SerializerMethodField()
    fornecedor_cnpj = serializers.SerializerMethodField()
    contraparte_nome = serializers.SerializerMethodField()
    pode_aplicar = serializers.SerializerMethodField()
    pode_cancelar = serializers.SerializerMethodField()
    pode_editar = serializers.SerializerMethodField()
    pode_editar_completo = serializers.SerializerMethodField()
    pode_excluir = serializers.SerializerMethodField()
    possui_movimento = serializers.SerializerMethodField()
    possui_movimento_ativo = serializers.SerializerMethodField()
    possui_apenas_movimentos_estornados = serializers.SerializerMethodField()
    possui_aplicacao = serializers.SerializerMethodField()
    possui_aplicacao_ativa = serializers.SerializerMethodField()
    possui_estorno = serializers.SerializerMethodField()
    possui_vinculo_origem = serializers.SerializerMethodField()
    motivo_bloqueio_exclusao = serializers.SerializerMethodField()
    saldo_integral_reaberto = serializers.SerializerMethodField()
    movimentos = BaixaFinanceiraSerializer(many=True, read_only=True)

    class Meta:
        model = CreditoFinanceiro
        fields = '__all__'

    def _flags(self, obj: CreditoFinanceiro) -> dict[str, bool]:
        cached = getattr(obj, '_credito_operational_flags_cache', None)
        if cached is None:
            cached = credito_operational_flags(obj)
            obj._credito_operational_flags_cache = cached
        return cached

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get('detail'):
            data.pop('movimentos', None)
        return data

    def get_status_label(self, obj) -> str:
        return credito_status_label(obj.status)

    def get_tipo_label(self, obj) -> str:
        return obj.get_tipo_display()

    def get_origem_tipo_label(self, obj) -> str:
        return obj.get_origem_tipo_display()

    def get_cliente_nome(self, obj) -> str:
        if not obj.cliente_id:
            return ''
        c = obj.cliente
        return (c.razao_social or c.nome_fantasia or '').strip()

    def get_cliente_cnpj(self, obj) -> str:
        if not obj.cliente_id:
            return ''
        return (obj.cliente.cnpj or '').strip()

    def get_fornecedor_nome(self, obj) -> str:
        if not obj.fornecedor_id:
            return ''
        f = obj.fornecedor
        return (f.razao_social or f.nome_fantasia or '').strip()

    def get_fornecedor_cnpj(self, obj) -> str:
        if not obj.fornecedor_id:
            return ''
        return (obj.fornecedor.cnpj or '').strip()

    def get_contraparte_nome(self, obj) -> str:
        if obj.tipo == CreditoFinanceiro.Tipo.CLIENTE:
            return self.get_cliente_nome(obj)
        return self.get_fornecedor_nome(obj)

    def get_pode_aplicar(self, obj) -> bool:
        return self._flags(obj)['pode_aplicar']

    def get_pode_cancelar(self, obj) -> bool:
        return self._flags(obj)['pode_cancelar']

    def get_pode_editar(self, obj) -> bool:
        return self._flags(obj)['pode_editar']

    def get_pode_editar_completo(self, obj) -> bool:
        return self._flags(obj)['pode_editar_completo']

    def get_pode_excluir(self, obj) -> bool:
        return self._flags(obj)['pode_excluir']

    def get_possui_movimento(self, obj) -> bool:
        return self._flags(obj)['possui_movimento']

    def get_possui_aplicacao(self, obj) -> bool:
        return self._flags(obj)['possui_aplicacao']

    def get_possui_estorno(self, obj) -> bool:
        return self._flags(obj)['possui_estorno']

    def get_possui_movimento_ativo(self, obj) -> bool:
        return self._flags(obj)['possui_movimento_ativo']

    def get_possui_apenas_movimentos_estornados(self, obj) -> bool:
        return self._flags(obj)['possui_apenas_movimentos_estornados']

    def get_possui_aplicacao_ativa(self, obj) -> bool:
        return self._flags(obj)['possui_aplicacao_ativa']

    def get_possui_vinculo_origem(self, obj) -> bool:
        return self._flags(obj)['possui_vinculo_origem']

    def get_motivo_bloqueio_exclusao(self, obj) -> str:
        return self._flags(obj)['motivo_bloqueio_exclusao']

    def get_saldo_integral_reaberto(self, obj) -> bool:
        return self._flags(obj)['saldo_integral_reaberto']


class TituloFinanceiroCreateSerializer(serializers.Serializer):
    numero = serializers.CharField(required=False, allow_blank=True, max_length=40)
    cliente = serializers.IntegerField(required=False, allow_null=True)
    fornecedor = serializers.IntegerField(required=False, allow_null=True)
    tipo_lancamento = serializers.ChoiceField(choices=TituloFinanceiro.TipoLancamentoPagar.choices, required=False, allow_blank=True)
    descricao = serializers.CharField(required=False, allow_blank=True, max_length=255)
    competencia = serializers.DateField(required=False, allow_null=True)
    tipo_tributo = serializers.ChoiceField(choices=TituloFinanceiro.TipoTributo.choices, required=False, allow_blank=True)
    periodo_apuracao = serializers.CharField(required=False, allow_blank=True, max_length=80)
    numero_guia = serializers.CharField(required=False, allow_blank=True, max_length=80)
    codigo_receita = serializers.CharField(required=False, allow_blank=True, max_length=40)
    parcelas = serializers.ListField(required=False)
    documento_origem = serializers.CharField(required=False, allow_blank=True, max_length=80)
    origem_tipo = serializers.ChoiceField(choices=TituloFinanceiro.OrigemTipo.choices, required=False)
    origem_id = serializers.IntegerField(required=False, allow_null=True)
    origem_numero = serializers.CharField(required=False, allow_blank=True)
    origem_descricao = serializers.CharField(required=False, allow_blank=True)
    origem_data = serializers.DateField(required=False, allow_null=True)
    data_emissao = serializers.DateField()
    data_vencimento = serializers.DateField()
    valor_original = serializers.DecimalField(max_digits=14, decimal_places=2)
    forma_pagamento_prevista_codigo = serializers.ChoiceField(choices=FormaPagamentoCodigo.CHOICES, required=False, allow_blank=True)
    conta_financeira_prevista = serializers.IntegerField(required=False, allow_null=True)
    categoria = serializers.IntegerField(required=False, allow_null=True)
    centro_custo = serializers.IntegerField(required=False, allow_null=True)
    observacoes = serializers.CharField(required=False, allow_blank=True)
    gerar_parcelas = serializers.BooleanField(default=False)
    quantidade_parcelas = serializers.IntegerField(default=1, min_value=1, max_value=120)
    intervalo_dias = serializers.IntegerField(default=30, min_value=0)
    primeiro_vencimento_dias = serializers.IntegerField(default=0, min_value=0)


class BaixaCreateSerializer(serializers.Serializer):
    data_baixa = serializers.DateField()
    valor = serializers.DecimalField(max_digits=14, decimal_places=2)
    conta_financeira = serializers.IntegerField(required=False, allow_null=True)
    forma_pagamento_codigo = serializers.ChoiceField(choices=FormaPagamentoCodigo.CHOICES)
    parcela = serializers.IntegerField(required=False, allow_null=True)
    juros = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    multa = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    desconto = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    tarifa = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    observacoes = serializers.CharField(required=False, allow_blank=True)


class AbatimentoCreateSerializer(serializers.Serializer):
    data = serializers.DateField()
    valor = serializers.DecimalField(max_digits=14, decimal_places=2)
    parcela = serializers.IntegerField(required=False, allow_null=True)
    motivo = serializers.CharField(max_length=255)
    observacoes = serializers.CharField(required=False, allow_blank=True)
    documento_referencia = serializers.CharField(required=False, allow_blank=True, max_length=80)


class CreditoCreateSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=CreditoFinanceiro.Tipo.choices)
    cliente = serializers.IntegerField(required=False, allow_null=True)
    fornecedor = serializers.IntegerField(required=False, allow_null=True)
    valor_original = serializers.DecimalField(max_digits=14, decimal_places=2)
    data_credito = serializers.DateField()
    motivo = serializers.CharField(max_length=255)
    origem_tipo = serializers.ChoiceField(choices=CreditoFinanceiro.OrigemTipo.choices, required=False)
    origem_descricao = serializers.CharField(required=False, allow_blank=True, max_length=255)
    origem_numero = serializers.CharField(required=False, allow_blank=True, max_length=80)
    observacoes = serializers.CharField(required=False, allow_blank=True)


class AplicarCreditoSerializer(serializers.Serializer):
    titulo = serializers.IntegerField()
    valor = serializers.DecimalField(max_digits=14, decimal_places=2)
    data = serializers.DateField()
    parcela = serializers.IntegerField(required=False, allow_null=True)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=255)
    observacoes = serializers.CharField(required=False, allow_blank=True)


class CancelarCreditoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)


class CreditoUpdateSerializer(serializers.Serializer):
    cliente = serializers.IntegerField(required=False, allow_null=True)
    fornecedor = serializers.IntegerField(required=False, allow_null=True)
    valor_original = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    origem_tipo = serializers.ChoiceField(choices=CreditoFinanceiro.OrigemTipo.choices, required=False)
    origem_numero = serializers.CharField(required=False, allow_blank=True, max_length=80)
    origem_descricao = serializers.CharField(required=False, allow_blank=True, max_length=255)
    data_credito = serializers.DateField(required=False)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=255)
    observacoes = serializers.CharField(required=False, allow_blank=True)


class ExcluirMotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)


class ReembolsoCreditoSerializer(serializers.Serializer):
    valor = serializers.DecimalField(max_digits=14, decimal_places=2)
    data = serializers.DateField()
    conta_financeira = serializers.IntegerField()
    forma_pagamento_codigo = serializers.ChoiceField(choices=FormaPagamentoCodigo.CHOICES)
    observacoes = serializers.CharField(max_length=500)


class EstornoBaixaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)


class CancelarTituloSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)
