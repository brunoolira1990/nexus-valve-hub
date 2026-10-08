from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from apps.cadastros.models import Fornecedor
from apps.produtos.models import Produto

from .cotacao_fornecedor_service import calcular_custo_resposta, classificar_completude_resposta, normalizar_tipo_frete
from .models import (
    CotacaoFornecedor,
    Proposta,
    CotacaoFornecedorItem,
    CotacaoFornecedorHistorico,
    CotacaoFornecedorParticipante,
    CotacaoFornecedorRespostaItem,
    ItemProposta,
)


class CotacaoFornecedorHistoricoSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CotacaoFornecedorHistorico
        fields = ('id', 'evento', 'descricao', 'dados_json', 'usuario', 'usuario_nome', 'criado_em')
        read_only_fields = fields

    def get_usuario_nome(self, obj):
        return obj.usuario.get_username() if obj.usuario_id else ''


class CotacaoFornecedorRespostaItemSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.IntegerField(source='participante.fornecedor_id', read_only=True)
    fornecedor_nome = serializers.CharField(source='participante.fornecedor.razao_social', read_only=True)
    selecionada_por_nome = serializers.SerializerMethodField(read_only=True)
    completude = serializers.SerializerMethodField(read_only=True)
    calculo_custo = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CotacaoFornecedorRespostaItem
        fields = (
            'id', 'participante', 'cotacao_item', 'fornecedor_id', 'fornecedor_nome',
            'preco_unitario', 'preco_unitario_bruto', 'desconto', 'quantidade_atendida',
            'unidade_cotada', 'fator_conversao', 'prazo_entrega', 'condicao_pagamento',
            'frete', 'frete_tipo', 'frete_tipo_codigo', 'ipi_custo', 'icms_st_custo',
            'outros_tributos_custo', 'despesas_adicionais', 'marca_fabricante', 'validade',
            'observacao', 'status_item', 'completude', 'calculo_custo',
            'selecionada_como_referencia', 'selecionada_por', 'selecionada_por_nome', 'selecionada_em',
        )
        read_only_fields = ('selecionada_por', 'selecionada_em', 'selecionada_como_referencia')

    def get_selecionada_por_nome(self, obj):
        return getattr(obj.selecionada_por, 'get_username', lambda: '')() if obj.selecionada_por else ''

    def get_completude(self, obj):
        return classificar_completude_resposta(obj, obj.cotacao_item)

    def get_calculo_custo(self, obj):
        result = calcular_custo_resposta(obj, obj.cotacao_item)
        return {key: str(value) if isinstance(value, Decimal) else value for key, value in result.items()}


class CotacaoFornecedorItemSerializer(serializers.ModelSerializer):
    item_proposta_id = serializers.PrimaryKeyRelatedField(
        source='item_proposta', queryset=ItemProposta.objects.all(),
    )
    produto_id = serializers.IntegerField(read_only=True)
    produto_nome = serializers.SerializerMethodField(read_only=True)
    respostas = CotacaoFornecedorRespostaItemSerializer(many=True, read_only=True)

    class Meta:
        model = CotacaoFornecedorItem
        fields = ('id', 'item_proposta_id', 'produto_id', 'produto_nome', 'produto_snapshot', 'descricao_item', 'unidade', 'quantidade', 'observacao_tecnica', 'status', 'respostas')
        read_only_fields = ('produto_id', 'produto_nome', 'produto_snapshot', 'status', 'respostas')

    def get_produto_nome(self, obj):
        return getattr(obj.produto, 'descricao', '') if obj.produto_id else (obj.produto_snapshot or {}).get('descricao', '')

    def validate_item_proposta_id(self, value):
        proposta_id = self.context.get('proposta_id')
        if proposta_id and value.proposta_id != int(proposta_id):
            raise serializers.ValidationError('O item não pertence à Proposta da cotação.')
        return value


class CotacaoFornecedorItemInputSerializer(serializers.Serializer):
    item_proposta_id = serializers.PrimaryKeyRelatedField(queryset=ItemProposta.objects.all(), required=False, allow_null=True)
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all(), required=False, allow_null=True)
    descricao_item = serializers.CharField(required=False, allow_blank=True)
    unidade = serializers.CharField(required=False, allow_blank=True)
    quantidade = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    observacao_tecnica = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        item = attrs.get('item_proposta_id')
        proposta_id = self.context.get('proposta_id')
        if item is not None:
            if proposta_id is None or item.proposta_id != int(proposta_id):
                raise serializers.ValidationError({'item_proposta_id': 'O item deve pertencer à Proposta da cotação.'})
            if any(attrs.get(key) not in (None, '') for key in ('descricao_item', 'unidade', 'produto_id')):
                raise serializers.ValidationError('Payload ambíguo: itens vinculados não aceitam campos manuais.')
            return attrs
        if not attrs.get('descricao_item', '').strip():
            raise serializers.ValidationError({'descricao_item': 'Descrição é obrigatória para item manual.'})
        if not attrs.get('unidade', '').strip():
            raise serializers.ValidationError({'unidade': 'Unidade é obrigatória para item manual.'})
        if attrs.get('quantidade') is None or attrs['quantidade'] <= 0:
            raise serializers.ValidationError({'quantidade': 'Quantidade deve ser maior que zero.'})
        return attrs


class CotacaoFornecedorParticipanteSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.PrimaryKeyRelatedField(source='fornecedor', queryset=Fornecedor.objects.filter(ativo=True))
    fornecedor_nome = serializers.CharField(source='fornecedor.razao_social', read_only=True)
    respostas = CotacaoFornecedorRespostaItemSerializer(many=True, read_only=True)

    class Meta:
        model = CotacaoFornecedorParticipante
        fields = ('id', 'fornecedor_id', 'fornecedor_nome', 'status', 'enviado_em', 'respondido_em', 'observacao', 'respostas')
        read_only_fields = ('status', 'enviado_em', 'respondido_em', 'respostas')


class CotacaoFornecedorSerializer(serializers.ModelSerializer):
    proposta_id = serializers.PrimaryKeyRelatedField(source='proposta', read_only=True)
    responsavel_nome = serializers.SerializerMethodField(read_only=True)
    itens = CotacaoFornecedorItemSerializer(many=True, read_only=True)
    participantes = CotacaoFornecedorParticipanteSerializer(many=True, read_only=True)

    class Meta:
        model = CotacaoFornecedor
        fields = ('id', 'numero', 'proposta_id', 'data', 'responsavel', 'responsavel_nome', 'prazo_resposta', 'observacao', 'status', 'criado_em', 'atualizado_em', 'itens', 'participantes')
        read_only_fields = ('numero', 'responsavel', 'responsavel_nome', 'status', 'criado_em', 'atualizado_em', 'itens', 'participantes')

    def get_responsavel_nome(self, obj):
        return obj.responsavel.get_username() if obj.responsavel_id else ''


class CotacaoFornecedorCreateSerializer(serializers.ModelSerializer):
    proposta = serializers.PrimaryKeyRelatedField(queryset=Proposta.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CotacaoFornecedor
        fields = ('proposta', 'data', 'prazo_resposta', 'observacao')

    def validate_proposta(self, value):
        if value is not None and not value.itens.exists():
            raise serializers.ValidationError('A Proposta precisa ter ao menos um item.')
        return value


class CotacaoFornecedorRespostaInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CotacaoFornecedorRespostaItem
        fields = (
            'participante', 'cotacao_item', 'preco_unitario', 'preco_unitario_bruto', 'desconto',
            'quantidade_atendida', 'unidade_cotada', 'fator_conversao', 'prazo_entrega',
            'condicao_pagamento', 'frete', 'frete_tipo', 'frete_tipo_codigo', 'ipi_custo',
            'icms_st_custo', 'outros_tributos_custo', 'despesas_adicionais', 'marca_fabricante',
            'validade', 'observacao', 'status_item',
        )

    def validate(self, attrs):
        participante = attrs['participante']
        item = attrs['cotacao_item']
        if participante.cotacao_id != item.cotacao_id:
            raise serializers.ValidationError('Participante e item pertencem a cotações diferentes.')
        status_item = attrs.get('status_item', CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO)
        if status_item == CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO and attrs.get('preco_unitario') is None:
            raise serializers.ValidationError({'preco_unitario': 'Preço unitário é obrigatório para resposta respondida.'})
        fator = attrs.get('fator_conversao')
        if fator is not None and fator <= 0:
            raise serializers.ValidationError({'fator_conversao': 'O fator de conversão deve ser maior que zero.'})
        tipo_codigo = attrs.get('frete_tipo_codigo')
        if tipo_codigo and tipo_codigo not in {'CIF', 'FOB', 'INCLUSO', 'OUTRO'}:
            raise serializers.ValidationError({'frete_tipo_codigo': 'Use CIF, FOB, INCLUSO ou OUTRO.'})
        bruto = attrs.get('preco_unitario_bruto')
        desconto = attrs.get('desconto')
        liquido = attrs.get('preco_unitario')
        if bruto is not None and bruto < 0:
            raise serializers.ValidationError({'preco_unitario_bruto': 'Preço bruto não pode ser negativo.'})
        if desconto is not None and desconto < 0:
            raise serializers.ValidationError({'desconto': 'Desconto não pode ser negativo.'})
        if bruto is not None and desconto is not None and liquido is not None:
            esperado = (bruto - desconto).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            if liquido != esperado:
                raise serializers.ValidationError({'preco_unitario': 'Preço unitário deve ser o preço líquido após desconto.'})
        if not tipo_codigo and attrs.get('frete_tipo'):
            normalizado = normalizar_tipo_frete('', attrs['frete_tipo'])
            if normalizado:
                attrs['frete_tipo_codigo'] = normalizado
        return attrs
