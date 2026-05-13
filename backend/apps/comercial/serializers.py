from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError
from rest_framework import serializers

from apps.cadastros.models import Cliente, Empresa, Fornecedor
from apps.corridas.models import Corrida
from apps.produtos.models import Produto
from apps.produtos.snapshot import build_produto_snapshot
from apps.comercial.payment_terms import compute_due_dates, parse_payment_condition
from apps.comercial.conversao_item_comercial import calcular_item_comercial_com_conversao
from apps.comercial.pedido_compra_finance import calcular_financeiro_item_pedido_compra
from apps.comercial.pedido_compra_numero import alocar_numero_pedido_compra
from apps.text_normalize import normalize_operational_fields, to_operational_upper

from .models import (
    ItemPedidoCompra,
    ItemPedidoVenda,
    ItemProposta,
    PedidoCompra,
    PedidoVenda,
    Proposta,
)
from . import pricing as price_rules


def _dec(v):
    return Decimal(str(v)) if v is not None else Decimal('0')


def _round(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'))


def recalcular_proposta(proposta: Proposta) -> None:
    total = Decimal('0')
    for it in proposta.itens.all():
        total += _dec(it.quantidade_negociada or it.quantidade) * _dec(it.preco_por_unidade_negociada or it.valor_unitario) - _dec(it.desconto)
    proposta.valor_total = total
    proposta.save(update_fields=['valor_total'])


def recalcular_pedido_venda(pedido: PedidoVenda) -> None:
    total = sum(
        (_dec(it.quantidade_negociada or it.quantidade) * _dec(it.preco_por_unidade_negociada or it.valor_unitario) for it in pedido.itens.all()),
        Decimal('0'),
    )
    pedido.valor_total = total
    pedido.save(update_fields=['valor_total'])


def recalcular_pedido_compra(pedido: PedidoCompra) -> None:
    total = sum((_dec(getattr(it, 'valor_total_item', None) or Decimal('0')) for it in pedido.itens.all()), Decimal('0'))
    pedido.valor_total = total
    pedido.save(update_fields=['valor_total'])


class ItemPropostaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    ipi_entrada_valor = serializers.SerializerMethodField(read_only=True)
    custo_carregado = serializers.SerializerMethodField(read_only=True)
    preco_base = serializers.SerializerMethodField(read_only=True)
    percentual_saida_total = serializers.SerializerMethodField(read_only=True)
    valor_carga_saida = serializers.SerializerMethodField(read_only=True)
    alertas_conversao = serializers.ListField(child=serializers.CharField(), required=False, read_only=True)

    class Meta:
        model = ItemProposta
        fields = (
            'id',
            'produto_id',
            'produto_nome',
            'quantidade',
            'unidade_negociada',
            'quantidade_negociada',
            'unidade_estoque_calculada',
            'quantidade_estoque_calculada',
            'peso_total_kg',
            'metros_total',
            'barras_total',
            'valor_unitario',
            'preco_por_unidade_negociada',
            'preco_por_kg',
            'preco_por_metro',
            'fator_conversao',
            'desconto',
            'custo_utilizado',
            'frete',
            'despesas',
            'ipi_entrada_percentual',
            'ipi_custo',
            'st_custo',
            'outros_impostos_custo',
            'custo_final',
            'icms_saida_percentual',
            'pis_saida_percentual',
            'cofins_saida_percentual',
            'ipi_saida_percentual',
            'regra_fiscal_id',
            'irpj_estimado_percentual',
            'csll_estimada_percentual',
            'comissao_percentual',
            'frete_saida',
            'outras_despesas_saida',
            'modo_preco',
            'preco_sugerido',
            'preco_final',
            'margem_resultante',
            'lucro_resultante',
            'descricao_avulsa',
            'ncm_avulso',
            'ipi_entrada_valor',
            'custo_carregado',
            'preco_base',
            'percentual_saida_total',
            'valor_carga_saida',
            'alertas_conversao',
            'snapshot_produto',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        produto = attrs.get('produto', self.instance.produto if self.instance else None)
        descricao_avulsa = to_operational_upper(
            attrs.get('descricao_avulsa', self.instance.descricao_avulsa if self.instance else '')
        ) or ''
        if not produto and not descricao_avulsa:
            raise serializers.ValidationError('Selecione um produto cadastrado ou informe uma descrição avulsa.')

        ps = _proposta_serializer_from_item_child(self)
        proposta_inst = ps.instance if ps and hasattr(ps, 'instance') else None
        incoming = _incoming_proposta(self)

        custo_utilizado = _dec(attrs.get('custo_utilizado', Decimal('0')))
        frete = _dec(attrs.get('frete', Decimal('0')))
        despesas = _dec(attrs.get('despesas', Decimal('0')))
        ipi_pct = _dec(attrs.get('ipi_entrada_percentual', Decimal('0')))
        ipi_legacy = _dec(attrs.get('ipi_custo', Decimal('0')))
        st = _dec(attrs.get('st_custo', Decimal('0')))
        outros = _dec(attrs.get('outros_impostos_custo', Decimal('0')))

        ipi_val = price_rules.compute_ipi_entrada_valor(custo_utilizado, ipi_pct, ipi_legacy)
        custo_carregado = price_rules.compute_custo_carregado(
            custo_utilizado,
            ipi_val,
            st,
            frete,
            despesas,
            outros,
        )
        preco_base = price_rules.compute_preco_base(custo_carregado)

        uf_origem = _resolve_uf_origem(incoming, proposta_inst)
        uf_destino = _resolve_uf_destino(incoming, proposta_inst)
        operacao = _resolve_operacao_fiscal(incoming, proposta_inst)

        if produto:
            ncm = produto.get_ncm_efetivo_codigo() or ''
        else:
            ncm = (
                attrs.get('ncm_avulso', self.instance.ncm_avulso if self.instance else '') or ''
            ).strip()

        regra = price_rules.find_regra_fiscal(ncm, uf_origem, uf_destino, operacao)
        if regra:
            attrs['icms_saida_percentual'] = _round(price_rules.float_to_dec(regra.aliquota_icms))
            attrs['pis_saida_percentual'] = _round(price_rules.float_to_dec(regra.aliquota_pis))
            attrs['cofins_saida_percentual'] = _round(price_rules.float_to_dec(regra.aliquota_cofins))
            attrs['ipi_saida_percentual'] = _round(price_rules.float_to_dec(regra.aliquota_ipi))
            attrs['regra_fiscal_id'] = regra.pk
        else:
            attrs['icms_saida_percentual'] = Decimal('0')
            attrs['pis_saida_percentual'] = Decimal('0')
            attrs['cofins_saida_percentual'] = Decimal('0')
            attrs['ipi_saida_percentual'] = Decimal('0')
            attrs['regra_fiscal_id'] = None

        irpj = _dec(attrs.get('irpj_estimado_percentual', Decimal('0')))
        csll = _dec(attrs.get('csll_estimada_percentual', Decimal('0')))
        comissao = _dec(attrs.get('comissao_percentual', Decimal('0')))
        frete_saida = _dec(attrs.get('frete_saida', Decimal('0')))
        outras_saida = _dec(attrs.get('outras_despesas_saida', Decimal('0')))

        pct_saida = price_rules.percentual_saida_total(
            attrs['icms_saida_percentual'],
            attrs['pis_saida_percentual'],
            attrs['cofins_saida_percentual'],
            attrs['ipi_saida_percentual'],
            irpj,
            csll,
            comissao,
        )

        modo_preco = (attrs.get('modo_preco') or 'sugerido').lower().strip()
        if modo_preco not in {'sugerido', 'manual'}:
            raise serializers.ValidationError({'modo_preco': "Use 'sugerido' ou 'manual'."})

        preco_sugerido = preco_base
        if modo_preco == 'manual':
            preco_final = _round(_dec(attrs.get('preco_final', Decimal('0'))))
        else:
            preco_final = preco_sugerido

        if preco_final < 0:
            raise serializers.ValidationError({'preco_final': 'Preço final não pode ser negativo.'})

        preco_ref = preco_sugerido if modo_preco == 'sugerido' else preco_final
        valor_carga = price_rules.compute_valor_carga_saida(preco_ref, pct_saida)
        lucro, margem = price_rules.compute_lucro_margem(
            preco_ref,
            custo_carregado,
            valor_carga,
            frete_saida,
            outras_saida,
        )

        attrs['modo_preco'] = modo_preco
        quantidade = _dec(attrs.get('quantidade', Decimal('0')))
        unidade_negociada = (attrs.get('unidade_negociada') or '').strip().upper()
        quantidade_neg = _dec(attrs.get('quantidade_negociada', quantidade)) or quantidade
        if not unidade_negociada and produto:
            unidade_negociada = (produto.get_unidade_venda_efetiva() or produto.unidade or 'PC').upper()
        calc = calcular_item_comercial_com_conversao(
            produto=produto,
            quantidade_negociada=quantidade_neg,
            unidade_negociada=unidade_negociada or 'PC',
            preco_por_unidade_negociada=_dec(attrs.get('preco_por_unidade_negociada', preco_final)),
        )
        attrs.update({k: v for k, v in calc.items() if k != 'alertas_conversao' and k != 'valor_total_calculado'})
        attrs['alertas_conversao'] = calc.get('alertas_conversao', [])
        attrs['custo_final'] = custo_carregado
        attrs['preco_sugerido'] = preco_sugerido
        attrs['preco_final'] = preco_final
        attrs['lucro_resultante'] = lucro
        attrs['margem_resultante'] = margem
        attrs['valor_unitario'] = preco_final
        attrs['descricao_avulsa'] = descricao_avulsa
        attrs['irpj_estimado_percentual'] = irpj
        attrs['csll_estimada_percentual'] = csll
        attrs['comissao_percentual'] = comissao
        attrs['frete_saida'] = frete_saida
        attrs['outras_despesas_saida'] = outras_saida
        attrs['ipi_entrada_percentual'] = ipi_pct
        if not produto:
            attrs['ncm_avulso'] = to_operational_upper(
                (attrs.get('ncm_avulso', self.instance.ncm_avulso if self.instance else '') or '')[:16]
            ) or ''
            attrs['snapshot_produto'] = {}
        else:
            attrs['ncm_avulso'] = ''
            attrs['snapshot_produto'] = build_produto_snapshot(produto)
        return attrs

    def get_produto_nome(self, obj):
        if obj.produto_id:
            return obj.produto.descricao
        return obj.descricao_avulsa or 'Item avulso'

    def _ipi_val_obj(self, obj: ItemProposta) -> Decimal:
        return price_rules.compute_ipi_entrada_valor(
            _dec(obj.custo_utilizado),
            _dec(obj.ipi_entrada_percentual),
            _dec(obj.ipi_custo),
        )

    def get_ipi_entrada_valor(self, obj: ItemProposta):
        return float(self._ipi_val_obj(obj))

    def get_custo_carregado(self, obj: ItemProposta):
        return float(
            price_rules.compute_custo_carregado(
                _dec(obj.custo_utilizado),
                self._ipi_val_obj(obj),
                _dec(obj.st_custo),
                _dec(obj.frete),
                _dec(obj.despesas),
                _dec(obj.outros_impostos_custo),
            )
        )

    def get_preco_base(self, obj: ItemProposta):
        cc = Decimal(str(self.get_custo_carregado(obj)))
        return float(price_rules.compute_preco_base(cc))

    def get_percentual_saida_total(self, obj: ItemProposta):
        t = price_rules.percentual_saida_total(
            _dec(obj.icms_saida_percentual),
            _dec(obj.pis_saida_percentual),
            _dec(obj.cofins_saida_percentual),
            _dec(obj.ipi_saida_percentual),
            _dec(obj.irpj_estimado_percentual),
            _dec(obj.csll_estimada_percentual),
            _dec(obj.comissao_percentual),
        )
        return float(t)

    def get_valor_carga_saida(self, obj: ItemProposta):
        modo = (obj.modo_preco or 'sugerido').lower()
        if modo == 'sugerido':
            ipi_val = self._ipi_val_obj(obj)
            cc = price_rules.compute_custo_carregado(
                _dec(obj.custo_utilizado),
                ipi_val,
                _dec(obj.st_custo),
                _dec(obj.frete),
                _dec(obj.despesas),
                _dec(obj.outros_impostos_custo),
            )
            preco_ref = price_rules.compute_preco_base(cc)
        else:
            preco_ref = _dec(obj.preco_final)
        pct = Decimal(str(self.get_percentual_saida_total(obj)))
        return float(price_rules.compute_valor_carga_saida(preco_ref, pct))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        ipi_val = self._ipi_val_obj(instance)
        cc = price_rules.compute_custo_carregado(
            _dec(instance.custo_utilizado),
            ipi_val,
            _dec(instance.st_custo),
            _dec(instance.frete),
            _dec(instance.despesas),
            _dec(instance.outros_impostos_custo),
        )
        pb = price_rules.compute_preco_base(cc)
        data['preco_sugerido'] = float(pb)
        data['alertas_conversao'] = []
        return data


def _proposta_serializer_from_item_child(child):
    parent = child.parent
    if isinstance(parent, serializers.ListSerializer):
        return parent.parent
    return parent


def _incoming_proposta(child) -> dict:
    return child.context.get('proposta_incoming') or {}


def _resolve_uf_origem(incoming: dict, proposta_inst: Proposta | None) -> str:
    eid = incoming.get('empresa_emitente_id')
    emp = None
    if isinstance(eid, Empresa):
        emp = eid
    elif eid is not None:
        emp = Empresa.objects.filter(pk=eid).first()
    if emp is None and proposta_inst is not None and proposta_inst.empresa_emitente_id:
        emp = proposta_inst.empresa_emitente
    if emp is None:
        emp = Empresa.objects.order_by('pk').first()
    return (emp.uf or '').strip().upper()[:2] if emp and emp.uf else ''


def _resolve_cliente_id(incoming: dict, proposta_inst: Proposta | None):
    cid = incoming.get('cliente_id')
    if cid is None and proposta_inst is not None:
        cid = proposta_inst.cliente_id
    return cid


def _resolve_uf_destino(incoming: dict, proposta_inst: Proposta | None) -> str:
    cid = _resolve_cliente_id(incoming, proposta_inst)
    if cid:
        if isinstance(cid, Cliente):
            return (cid.uf or '').strip().upper()[:2]
        row = Cliente.objects.filter(pk=cid).values('uf').first()
        if row:
            return (row.get('uf') or '').strip().upper()[:2]
    u = (incoming.get('uf_destino_avulso') or '').strip().upper()
    if len(u) == 2:
        return u
    if proposta_inst is not None:
        return (proposta_inst.uf_destino_avulso or '').strip().upper()[:2]
    return ''


def _resolve_operacao_fiscal(incoming: dict, proposta_inst: Proposta | None) -> str:
    return 'Saída'


def _apply_emitente_e_uf_operacao_saida(attrs: dict, instance: Proposta | None) -> None:
    """Fluxo comercial: operação sempre saída; UF origem derivada da empresa emitente."""
    n = Empresa.objects.count()
    emp = attrs.get('empresa_emitente')
    if emp is None and instance and instance.empresa_emitente_id:
        emp = instance.empresa_emitente
    if emp is None and n == 1:
        emp = Empresa.objects.order_by('pk').first()
    if n > 1 and emp is None:
        raise serializers.ValidationError({'empresa_emitente_id': 'Selecione a empresa emitente.'})
    if emp is not None:
        attrs['empresa_emitente'] = emp
    attrs['operacao_fiscal'] = 'Saída'
    attrs['uf_origem'] = ((emp.uf or '') if emp else '').strip().upper()[:2]


class PropostaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(),
        source='cliente',
        allow_null=True,
        required=False,
    )
    empresa_emitente_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source='empresa_emitente',
        allow_null=True,
        required=False,
    )
    empresa_emitente_nome = serializers.SerializerMethodField(read_only=True)
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemPropostaSerializer(many=True)

    class Meta:
        model = Proposta
        fields = (
            'id',
            'numero',
            'cliente_id',
            'cliente_nome',
            'cliente_avulso_nome',
            'empresa_emitente_id',
            'empresa_emitente_nome',
            'data',
            'validade',
            'vendedor',
            'status',
            'condicao_pagamento_texto',
            'dias_parcelas',
            'quantidade_parcelas',
            'vencimentos_previstos',
            'valor_total',
            'uf_origem',
            'uf_destino_avulso',
            'operacao_fiscal',
            'itens',
        )

    def is_valid(self, raise_exception=False):
        if getattr(self, 'initial_data', None) and isinstance(self.initial_data, dict):
            self.context['proposta_incoming'] = self.initial_data
        return super().is_valid(raise_exception=raise_exception)

    def get_cliente_nome(self, obj):
        if obj.cliente_id:
            return obj.cliente.razao_social
        return obj.cliente_avulso_nome or 'Cliente avulso'

    def get_empresa_emitente_nome(self, obj):
        if obj.empresa_emitente_id:
            return obj.empresa_emitente.razao_social
        return ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cliente_id'] = instance.cliente_id
        data['empresa_emitente_id'] = instance.empresa_emitente_id
        data['data'] = instance.data.isoformat()
        data['validade'] = instance.validade.isoformat()
        data['vencimentos_previstos'] = [d.isoformat() for d in instance.vencimentos_previstos]
        data['valor_total'] = float(instance.valor_total)
        data['operacao_fiscal'] = 'Saída'
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'numero', 'vendedor', 'status', 'condicao_pagamento_texto'})
        cliente = attrs.get('cliente', self.instance.cliente if self.instance else None)
        cliente_avulso_nome = to_operational_upper(
            attrs.get('cliente_avulso_nome', self.instance.cliente_avulso_nome if self.instance else '')
        ) or ''
        if not cliente and not cliente_avulso_nome:
            raise serializers.ValidationError({'cliente_id': 'Selecione cliente cadastrado ou informe cliente avulso.'})
        attrs['cliente_avulso_nome'] = cliente_avulso_nome

        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        data_base = attrs.get('data', self.instance.data if self.instance else None)
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        attrs['vencimentos_previstos'] = compute_due_dates(data_base, dias)
        _apply_emitente_e_uf_operacao_saida(attrs, self.instance)
        return attrs

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        proposta = Proposta.objects.create(**validated_data)
        for item in itens_data:
            ItemProposta.objects.create(proposta=proposta, **item)
        recalcular_proposta(proposta)
        return proposta

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemProposta.objects.create(proposta=instance, **item)
        recalcular_proposta(instance)
        return instance


class ItemPedidoVendaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
    )
    corrida_id = serializers.PrimaryKeyRelatedField(
        queryset=Corrida.objects.all(),
        source='corrida',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    corrida_numero = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemPedidoVenda
        fields = (
            'id',
            'produto_id',
            'produto_nome',
            'quantidade',
            'unidade_negociada',
            'quantidade_negociada',
            'unidade_estoque_calculada',
            'quantidade_estoque_calculada',
            'peso_total_kg',
            'metros_total',
            'barras_total',
            'valor_unitario',
            'preco_por_unidade_negociada',
            'preco_por_kg',
            'preco_por_metro',
            'fator_conversao',
            'corrida_id',
            'corrida_numero',
            'snapshot_produto',
        )

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_corrida_numero(self, obj):
        return obj.corrida.numero if obj.corrida_id else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['corrida_id'] = instance.corrida_id
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'unidade_negociada'})
        produto = attrs.get('produto', self.instance.produto if self.instance else None)
        quantidade = _dec(attrs.get('quantidade', self.instance.quantidade if self.instance else Decimal('0')))
        unidade_negociada = (attrs.get('unidade_negociada', self.instance.unidade_negociada if self.instance else '') or '').strip().upper()
        quantidade_neg = _dec(attrs.get('quantidade_negociada', quantidade)) or quantidade
        preco = _dec(
            attrs.get(
                'preco_por_unidade_negociada',
                attrs.get('valor_unitario', self.instance.valor_unitario if self.instance else Decimal('0')),
            )
        )
        calc = calcular_item_comercial_com_conversao(
            produto=produto,
            quantidade_negociada=quantidade_neg,
            unidade_negociada=unidade_negociada,
            preco_por_unidade_negociada=preco,
        )
        attrs.update({k: v for k, v in calc.items() if k not in {'alertas_conversao', 'valor_total_calculado'}})
        if produto:
            attrs['snapshot_produto'] = build_produto_snapshot(produto)
        return attrs


class PedidoVendaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(),
        source='cliente',
    )
    empresa_emitente_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source='empresa_emitente',
        allow_null=True,
        required=False,
    )
    empresa_emitente_nome = serializers.SerializerMethodField(read_only=True)
    proposta_id = serializers.PrimaryKeyRelatedField(
        queryset=Proposta.objects.all(),
        source='proposta',
        allow_null=True,
        required=False,
    )
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemPedidoVendaSerializer(many=True)

    class Meta:
        model = PedidoVenda
        fields = (
            'id',
            'numero',
            'empresa_emitente_id',
            'empresa_emitente_nome',
            'cliente_id',
            'cliente_nome',
            'data',
            'status',
            'condicao_pagamento_texto',
            'dias_parcelas',
            'quantidade_parcelas',
            'vencimentos_previstos',
            'valor_total',
            'proposta_id',
            'itens',
        )

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social

    def get_empresa_emitente_nome(self, obj):
        if obj.empresa_emitente_id:
            return obj.empresa_emitente.razao_social
        return ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cliente_id'] = instance.cliente_id
        data['empresa_emitente_id'] = instance.empresa_emitente_id
        data['data'] = instance.data.isoformat()
        data['vencimentos_previstos'] = [d.isoformat() for d in instance.vencimentos_previstos]
        data['valor_total'] = float(instance.valor_total)
        data['proposta_id'] = instance.proposta_id
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'numero', 'status', 'condicao_pagamento_texto'})
        n = Empresa.objects.count()
        emp = attrs.get('empresa_emitente')
        if emp is None and self.instance and self.instance.empresa_emitente_id:
            emp = self.instance.empresa_emitente
        if emp is None and n == 1:
            emp = Empresa.objects.order_by('pk').first()
        if n > 1 and emp is None:
            raise serializers.ValidationError({'empresa_emitente_id': 'Selecione a empresa emitente.'})
        if emp is not None:
            attrs['empresa_emitente'] = emp
        proposta = attrs.get('proposta', self.instance.proposta if self.instance else None)
        if proposta:
            if not self.instance and PedidoVenda.objects.filter(proposta=proposta).exists():
                raise serializers.ValidationError(
                    {'proposta_id': 'Esta proposta já foi convertida em pedido de venda.'}
                )
            if not proposta.cliente_id:
                raise serializers.ValidationError(
                    {'proposta_id': 'Esta proposta possui cliente avulso. Vincule/crie cliente cadastrado antes de converter.'}
                )
            if proposta.itens.filter(produto__isnull=True).exists():
                raise serializers.ValidationError(
                    {'proposta_id': 'Esta proposta possui item avulso. Vincule/crie produto cadastrado antes de converter.'}
                )
        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        data_base = attrs.get('data', self.instance.data if self.instance else None)
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        attrs['vencimentos_previstos'] = compute_due_dates(data_base, dias)
        return attrs

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        pedido = PedidoVenda.objects.create(**validated_data)
        for item in itens_data:
            ItemPedidoVenda.objects.create(pedido=pedido, **item)
        recalcular_pedido_venda(pedido)
        return pedido

    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemPedidoVenda.objects.create(pedido=instance, **item)
        recalcular_pedido_venda(instance)
        return instance


class ItemPedidoCompraSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemPedidoCompra
        fields = (
            'id',
            'produto_id',
            'produto_nome',
            'quantidade',
            'unidade_negociada',
            'quantidade_negociada',
            'unidade_estoque_calculada',
            'quantidade_estoque_calculada',
            'peso_total_kg',
            'metros_total',
            'barras_total',
            'valor_unitario',
            'preco_por_unidade_negociada',
            'preco_por_kg',
            'preco_por_metro',
            'fator_conversao',
            'snapshot_produto',
            'ipi_percentual',
            'ipi_valor',
            'icms_st_percentual',
            'icms_st_valor',
            'desconto_valor',
            'frete_valor',
            'outras_despesas_valor',
            'valor_produtos',
            'valor_total_item',
        )

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'unidade_negociada'})
        produto = attrs.get('produto', self.instance.produto if self.instance else None)
        if not produto:
            raise serializers.ValidationError({'produto_id': 'Selecione o produto Nexus para o item.'})
        quantidade = _dec(attrs.get('quantidade', self.instance.quantidade if self.instance else Decimal('0')))
        unidade_negociada = (attrs.get('unidade_negociada', self.instance.unidade_negociada if self.instance else '') or '').strip().upper()
        if not unidade_negociada:
            raise serializers.ValidationError({'unidade_negociada': 'Selecione a unidade negociada.'})
        quantidade_neg = _dec(attrs.get('quantidade_negociada', quantidade)) or quantidade
        preco = _dec(
            attrs.get(
                'preco_por_unidade_negociada',
                attrs.get('valor_unitario', self.instance.valor_unitario if self.instance else Decimal('0')),
            )
        )

        def gv(key):
            if key in attrs and attrs[key] is not None:
                return _dec(attrs[key])
            if self.instance is not None:
                return _dec(getattr(self.instance, key))
            return Decimal('0')

        neg_checks = (
            ('ipi_percentual', 'IPI % não pode ser negativo.'),
            ('ipi_valor', 'Valor de IPI não pode ser negativo.'),
            ('icms_st_percentual', 'ICMS ST % não pode ser negativo.'),
            ('icms_st_valor', 'Valor de ICMS ST não pode ser negativo.'),
            ('desconto_valor', 'Desconto não pode ser negativo.'),
            ('frete_valor', 'Frete não pode ser negativo.'),
            ('outras_despesas_valor', 'Outras despesas não podem ser negativas.'),
        )
        for key, msg in neg_checks:
            if gv(key) < 0:
                raise serializers.ValidationError({key: msg})

        calc = calcular_item_comercial_com_conversao(
            produto=produto,
            quantidade_negociada=quantidade_neg,
            unidade_negociada=unidade_negociada,
            preco_por_unidade_negociada=preco,
            contexto='compra',
        )
        attrs.update({k: v for k, v in calc.items() if k not in {'alertas_conversao', 'valor_total_calculado'}})
        if produto:
            attrs['snapshot_produto'] = build_produto_snapshot(produto)

        qn = _dec(attrs.get('quantidade_negociada', quantidade_neg))
        pr = _dec(attrs.get('preco_por_unidade_negociada', preco))
        fin = calcular_financeiro_item_pedido_compra(
            quantidade_negociada=qn,
            preco_por_unidade_negociada=pr,
            ipi_percentual=gv('ipi_percentual'),
            ipi_valor_informado=gv('ipi_valor'),
            icms_st_percentual=gv('icms_st_percentual'),
            icms_st_valor_informado=gv('icms_st_valor'),
            desconto_valor=gv('desconto_valor'),
            frete_valor=gv('frete_valor'),
            outras_despesas_valor=gv('outras_despesas_valor'),
        )
        attrs.update(fin)
        return attrs


class PedidoCompraSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemPedidoCompraSerializer(many=True)
    data_prevista_entrega = serializers.DateField(required=False, allow_null=True)
    resumo_financeiro_pedido = serializers.SerializerMethodField(read_only=True)
    numero = serializers.CharField(max_length=32, required=False, allow_blank=True)

    class Meta:
        model = PedidoCompra
        fields = (
            'id',
            'numero',
            'fornecedor_id',
            'fornecedor_nome',
            'data',
            'status',
            'condicao_pagamento_texto',
            'dias_parcelas',
            'quantidade_parcelas',
            'vencimentos_previstos',
            'valor_total',
            'prazo_entrega_texto',
            'data_prevista_entrega',
            'resumo_financeiro_pedido',
            'itens',
        )

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor.razao_social

    def get_resumo_financeiro_pedido(self, obj):
        sub = ipi = st = desc = frete = outras = Decimal('0')
        for it in obj.itens.all():
            sub += _dec(it.valor_produtos)
            ipi += _dec(it.ipi_valor)
            st += _dec(it.icms_st_valor)
            desc += _dec(it.desconto_valor)
            frete += _dec(it.frete_valor)
            outras += _dec(it.outras_despesas_valor)
        return {
            'subtotal_produtos': float(_round(sub)),
            'total_ipi': float(_round(ipi)),
            'total_icms_st': float(_round(st)),
            'total_descontos': float(_round(desc)),
            'total_frete': float(_round(frete)),
            'total_outras_despesas': float(_round(outras)),
            'valor_total_pedido': float(_round(_dec(obj.valor_total))),
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['fornecedor_id'] = instance.fornecedor_id
        data['data'] = instance.data.isoformat()
        data['vencimentos_previstos'] = [d.isoformat() for d in instance.vencimentos_previstos]
        data['valor_total'] = float(instance.valor_total)
        data['data_prevista_entrega'] = instance.data_prevista_entrega.isoformat() if instance.data_prevista_entrega else None
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None:
            attrs.pop('numero', None)
        else:
            raw_num = (attrs.get('numero') or '').strip()
            if raw_num:
                attrs['numero'] = raw_num
                if PedidoCompra.objects.filter(numero=raw_num).exists():
                    raise serializers.ValidationError(
                        {'numero': ['Já existe um pedido de compra com este número.']}
                    )
            else:
                attrs.pop('numero', None)

        normalize_operational_fields(attrs, {'status', 'condicao_pagamento_texto', 'prazo_entrega_texto'})
        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        data_base = attrs.get('data', self.instance.data if self.instance else None)
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        attrs['vencimentos_previstos'] = compute_due_dates(data_base, dias)
        itens = attrs.get('itens')
        if self.instance is None:
            if not itens:
                raise serializers.ValidationError({'itens': 'Inclua ao menos um item no pedido.'})
        elif itens is not None and len(itens) == 0:
            raise serializers.ValidationError({'itens': 'O pedido deve manter ao menos um item.'})
        return attrs

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        data_pedido = validated_data['data']
        if not (validated_data.get('numero') or '').strip():
            validated_data['numero'] = alocar_numero_pedido_compra(data_pedido)
        try:
            pedido = PedidoCompra.objects.create(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'numero': ['Já existe um pedido de compra com este número.']}
            ) from None
        for item in itens_data:
            ItemPedidoCompra.objects.create(pedido=pedido, **item)
        recalcular_pedido_compra(pedido)
        return pedido

    def update(self, instance, validated_data):
        validated_data.pop('numero', None)
        itens_data = validated_data.pop('itens', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {'detail': 'Não foi possível salvar o pedido de compra. Verifique se o número já existe.'}
            ) from None
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemPedidoCompra.objects.create(pedido=instance, **item)
        recalcular_pedido_compra(instance)
        return instance
