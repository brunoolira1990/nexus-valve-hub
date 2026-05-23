from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.cadastros.models import Cliente, Empresa, Fornecedor, Transportadora
from apps.fiscal.nfe_saida_bloqueio import (
    CAMPOS_COMPLEMENTARES_ITEM_NFE,
    CAMPOS_COMPLEMENTARES_NFE,
    MSG_DADOS_COMPLEMENTARES_BLOQUEADOS,
    MSG_ITENS_ORIGEM_COMERCIAL,
    dados_complementares_editaveis,
    itens_comerciais_editaveis,
    nf_ja_finalizada_operacionalmente,
    origem_comercial_travada,
)
from apps.comercial.models import ItemPedidoCompra, PedidoCompra, PedidoVenda
from apps.corridas.models import Corrida
from apps.produtos.conversao_medidas import ConversaoErro, converter_quantidade_produto
from apps.produtos.models import Produto
from apps.produtos.snapshot import build_produto_snapshot
from apps.regras_fiscais.entrada_fiscal import (
    avaliar_item_entrada_fiscal,
    montar_contexto_fiscal_entrada,
    montar_resumo_fiscal_conferencia,
)
from apps.text_normalize import normalize_operational_fields
from apps.qualidade.certificado_pdf import gerar_certificado_pdf
from apps.qualidade.models import Certificado

from .atendimento_estoque import (
    criar_ou_atualizar_atendimento_item_antecipado,
    montar_resumo_atendimento_estoque_nf,
    sync_itens_nf_saida_antecipada,
    validar_troca_modo_atendimento,
)
from .estoque_services import (
    aplicar_todos_itens_entrada,
    aplicar_todos_itens_saida,
    reverter_todos_itens_entrada,
    reverter_todos_itens_saida,
)
from .atendimento_estoque import (
    dias_em_aberto_atendimento,
    listar_vinculos_item_conferencia,
    quantidade_alocada_item_conferencia,
    quantidade_disponivel_item_conferencia,
    quantidade_pendente_atendimento,
)
from .models import (
    AtendimentoEstoque,
    CTeEntrada,
    CTeHistoricoImportado,
    EventoCTeHistoricoImportado,
    EventoNFeSaidaHistoricaImportada,
    EventoNFeSaidaHistoricaPendente,
    ItemNFeEntrada,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaHistoricaImportada,
    ItemNFeSaida,
    ItemNFeSaidaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from .conferencia_pedido import (
    avaliar_elegibilidade_estoque_item_conferencia,
    build_snapshot_pedido,
    carregar_certificados_fornecedor_por_item_conferencia,
    item_pedido_resumo_dict,
    montar_resumo_elegibilidade_estoque,
    montar_resumo_pedido_conferencia,
    sugerir_itens_pedido_linha,
)
from .nfe_historica_fiscal import documento_tem_icmstot, extrair_totais_fiscais_documento


def _dec(v):
    return Decimal(str(v)) if v is not None else Decimal('0')


def _event_json_get(event_json: dict | None, *path: str) -> str:
    cur = event_json
    for key in path:
        if not isinstance(cur, dict):
            return ''
        cur = cur.get(key)
    if cur is None:
        return ''
    return str(cur).strip()


def _cancelamento_snapshot(obj: NFeSaidaHistoricaImportada) -> dict[str, str | bool | None]:
    """
    Resolve o estado efetivo/visual da nota priorizando evento de cancelamento.
    """
    evento_cancelamento = obj.eventos.filter(tipo_evento='110111').order_by('-data_evento', '-id').first()
    has_cancel_event = evento_cancelamento is not None
    if obj.cancelada or has_cancel_event:
        ev = obj.evento_cancelamento_json if isinstance(obj.evento_cancelamento_json, dict) else {}
        if has_cancel_event and (not ev):
            ev = evento_cancelamento.evento_json if isinstance(evento_cancelamento.evento_json, dict) else {}
        cstat_evento = _event_json_get(ev, 'retEvento', 'cStat') or _event_json_get(ev, 'retEvento', 'infEvento', 'cStat')
        motivo_evento = _event_json_get(ev, 'retEvento', 'xMotivo') or _event_json_get(ev, 'retEvento', 'infEvento', 'xMotivo')
        protocolo_evento = (
            obj.protocolo_evento
            or (evento_cancelamento.protocolo_evento if has_cancel_event else '')
            or _event_json_get(ev, 'retEvento', 'nProt')
            or _event_json_get(ev, 'retEvento', 'infEvento', 'nProt')
        )
        return {
            'cancelada': True,
            'status_visual': 'cancelada',
            'cstat_visual': cstat_evento or '101',
            'motivo_visual': motivo_evento or 'Cancelamento de NF-e homologado',
            'protocolo_cancelamento': protocolo_evento or '',
        }
    return {
        'cancelada': False,
        'status_visual': obj.status_documento or 'autorizada',
        'cstat_visual': obj.cstat or '',
        'motivo_visual': obj.xmotivo or '',
        'protocolo_cancelamento': '',
    }


def recalcular_valor_nf_entrada(nf: NFeEntrada) -> None:
    total = sum((_dec(it.valor) * _dec(it.quantidade) for it in nf.itens.all()), Decimal('0'))
    nf.valor_total = total
    nf.save(update_fields=['valor_total'])


def recalcular_valor_nf_saida(nf: NFeSaida) -> None:
    total = sum((_dec(it.valor) * _dec(it.quantidade) for it in nf.itens.all()), Decimal('0'))
    nf.valor_total = total
    nf.save(update_fields=['valor_total'])


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'))


def _norm_unit(value: str | None) -> str:
    return (value or '').strip().upper()


def _extract_prod_fields(prod_json: dict) -> dict:
    return {
        'codigo_fornecedor': str(prod_json.get('cProd') or '').strip(),
        'descricao_fornecedor': str(prod_json.get('xProd') or '').strip(),
        'ncm': str(prod_json.get('NCM') or '').strip(),
        'cfop': str(prod_json.get('CFOP') or '').strip(),
        'unidade_nf': _norm_unit(str(prod_json.get('uCom') or prod_json.get('uTrib') or '')),
        'quantidade_nf': _dec(prod_json.get('qCom') or prod_json.get('qTrib') or 0),
        'valor_unitario_nf': _dec(prod_json.get('vUnCom') or prod_json.get('vUnTrib') or 0),
        'valor_total_nf': _dec(prod_json.get('vProd') or 0),
    }


def _resolve_payment_terms(nf: NFeSaida) -> tuple[str, list[int]]:
    if nf.pedido_venda_id:
        pedido = nf.pedido_venda
        return (pedido.condicao_pagamento_texto or '', list(pedido.dias_parcelas or []))
    cliente = nf.cliente
    return (cliente.condicao_pagamento_texto or '', list(cliente.dias_parcelas or []))


def _build_titles(nf: NFeSaida) -> tuple[list, list[dict]]:
    days = list(nf.dias_parcelas or [])
    if not days:
        return ([], [])

    due_dates = [nf.data + timezone.timedelta(days=d) for d in days]
    count = len(days)
    if count <= 0:
        return (due_dates, [])

    total = _round_money(_dec(nf.valor_total))
    quota = _round_money(total / Decimal(count))
    titles: list[dict] = []
    accumulated = Decimal('0.00')

    for idx, (day, due_date) in enumerate(zip(days, due_dates), start=1):
        if idx < count:
            amount = quota
            accumulated += amount
        else:
            amount = _round_money(total - accumulated)
        titles.append(
            {
                'parcela': idx,
                'dias': int(day),
                'vencimento': due_date.isoformat(),
                'valor': str(amount),
                'status': 'aberto',
            }
        )
    return (due_dates, titles)


def sincronizar_financeiro_nf_saida(nf: NFeSaida) -> None:
    texto, days = _resolve_payment_terms(nf)
    nf.condicao_pagamento_texto = texto
    nf.dias_parcelas = days
    nf.quantidade_parcelas = len(days)
    due_dates, titles = _build_titles(nf)
    nf.vencimentos_finais = due_dates
    nf.titulos_receber = titles


class ItemNFeEntradaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all(), source='produto')
    corrida_id = serializers.PrimaryKeyRelatedField(
        queryset=Corrida.objects.all(),
        source='corrida',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    corrida_numero = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemNFeEntrada
        fields = ('id', 'produto_id', 'produto_nome', 'quantidade', 'valor', 'corrida_id', 'corrida_numero', 'snapshot_produto')

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_corrida_numero(self, obj):
        return obj.corrida.numero if obj.corrida_id else None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'unidade_negociada'})
        produto = attrs.get('produto', self.instance.produto if self.instance else None)
        if produto:
            attrs['snapshot_produto'] = build_produto_snapshot(produto)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['corrida_id'] = instance.corrida_id
        return data


class NFeEntradaSerializer(serializers.ModelSerializer):
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
    )
    pedido_compra_id = serializers.PrimaryKeyRelatedField(
        queryset=PedidoCompra.objects.all(),
        source='pedido_compra',
        allow_null=True,
        required=False,
    )
    cte_id = serializers.PrimaryKeyRelatedField(
        queryset=CTeEntrada.objects.all(),
        source='cte',
        allow_null=True,
        required=False,
    )
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    fornecedor_cnpj = serializers.SerializerMethodField(read_only=True)
    itens = ItemNFeEntradaSerializer(many=True)

    class Meta:
        model = NFeEntrada
        fields = (
            'id',
            'numero',
            'fornecedor_id',
            'fornecedor_nome',
            'fornecedor_cnpj',
            'data',
            'valor_total',
            'pedido_compra_id',
            'cte_id',
            'itens',
        )

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor.razao_social

    def get_fornecedor_cnpj(self, obj):
        return obj.fornecedor.cnpj

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'numero'})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['fornecedor_id'] = instance.fornecedor_id
        data['data'] = instance.data.isoformat()
        data['valor_total'] = float(instance.valor_total)
        data['pedido_compra_id'] = instance.pedido_compra_id
        data['cte_id'] = instance.cte_id
        return data

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        nf = NFeEntrada.objects.create(**validated_data)
        for item in itens_data:
            ItemNFeEntrada.objects.create(nf=nf, **item)
        recalcular_valor_nf_entrada(nf)
        try:
            aplicar_todos_itens_entrada(nf)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return nf

    @transaction.atomic
    def update(self, instance, validated_data):
        itens_data = validated_data.pop('itens', None)
        reverter_todos_itens_entrada(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if itens_data is not None:
            instance.itens.all().delete()
            for item in itens_data:
                ItemNFeEntrada.objects.create(nf=instance, **item)
        recalcular_valor_nf_entrada(instance)
        try:
            aplicar_todos_itens_entrada(instance)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return instance


class ItemNFeSaidaSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all(), source='produto')
    corrida_id = serializers.PrimaryKeyRelatedField(
        queryset=Corrida.objects.all(),
        source='corrida',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    corrida_numero = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemNFeSaida
        fields = (
            'id',
            'produto_id',
            'produto_nome',
            'quantidade',
            'valor',
            'corrida_id',
            'corrida_numero',
            'snapshot_produto',
            'snapshot_fiscal',
            'snapshot_comercial',
            'pedido_cliente_numero',
            'pedido_cliente_item',
            'observacao_item',
            'informacao_adicional_item',
        )

    def get_produto_nome(self, obj):
        return obj.produto.descricao

    def get_corrida_numero(self, obj):
        return obj.corrida.numero if obj.corrida_id else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['produto_id'] = instance.produto_id
        data['corrida_id'] = instance.corrida_id
        snap = instance.snapshot_produto or {}
        if snap.get('descricao'):
            data['produto_nome'] = snap['descricao']
        elif instance.produto_id:
            data['produto_nome'] = instance.produto.descricao
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        produto = attrs.get('produto', self.instance.produto if self.instance else None)
        if produto:
            attrs['snapshot_produto'] = build_produto_snapshot(produto)
        return attrs


def _gerar_ou_atualizar_certificado(nf: NFeSaida) -> None:
    Certificado.objects.filter(nf_saida=nf).delete()
    pdf = gerar_certificado_pdf(nf)
    Certificado.objects.create(nf_saida=nf, arquivo=pdf)


class NFeSaidaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all(), source='cliente')
    pedido_venda_id = serializers.PrimaryKeyRelatedField(
        queryset=PedidoVenda.objects.all(),
        source='pedido_venda',
        allow_null=True,
        required=False,
    )
    pedido_venda_numero = serializers.SerializerMethodField(read_only=True)
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    modo_atendimento_estoque_display = serializers.SerializerMethodField(read_only=True)
    resumo_atendimento_estoque = serializers.SerializerMethodField(read_only=True)
    origem_comercial_travada = serializers.SerializerMethodField(read_only=True)
    dados_complementares_editaveis = serializers.SerializerMethodField(read_only=True)
    itens_comerciais_editaveis = serializers.SerializerMethodField(read_only=True)
    transportadora_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora',
        allow_null=True,
        required=False,
    )
    transportadora_nome = serializers.SerializerMethodField(read_only=True)
    status_conferencia_display = serializers.SerializerMethodField(read_only=True)
    itens = ItemNFeSaidaSerializer(many=True)

    class Meta:
        model = NFeSaida
        fields = (
            'id',
            'numero',
            'cliente_id',
            'cliente_nome',
            'data',
            'valor_total',
            'modo_atendimento_estoque',
            'modo_atendimento_estoque_display',
            'status',
            'status_conferencia',
            'status_conferencia_display',
            'conferencia_validada_em',
            'conferencia_marcada_pronta_em',
            'conferencia_ultima_mensagem',
            'condicao_pagamento_texto',
            'dias_parcelas',
            'quantidade_parcelas',
            'vencimentos_finais',
            'titulos_receber',
            'pedido_venda_id',
            'pedido_venda_numero',
            'faturamento_pedido_venda_id',
            'observacao_origem',
            'resumo_atendimento_estoque',
            'origem_comercial_travada',
            'dados_complementares_editaveis',
            'itens_comerciais_editaveis',
            'transportadora_id',
            'transportadora_nome',
            'modalidade_frete',
            'valor_frete',
            'quantidade_volumes',
            'peso_bruto',
            'peso_liquido',
            'observacoes_nfe',
            'informacoes_adicionais',
            'pedido_cliente_numero',
            'pedido_cliente_observacao',
            'informacoes_fisco',
            'observacoes_internas',
            'especie_volumes',
            'marca_volumes',
            'numeracao_volumes',
            'placa_veiculo',
            'uf_veiculo',
            'itens',
        )
        read_only_fields = (
            'status_conferencia',
            'status_conferencia_display',
            'conferencia_validada_em',
            'conferencia_marcada_pronta_em',
            'conferencia_ultima_mensagem',
        )

    def get_pedido_venda_numero(self, obj):
        if obj.pedido_venda_id and obj.pedido_venda:
            return obj.pedido_venda.numero
        return ''

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social

    def get_modo_atendimento_estoque_display(self, obj):
        labels = {
            NFeSaida.ModoAtendimentoEstoque.IMEDIATO: 'Imediato',
            NFeSaida.ModoAtendimentoEstoque.ANTECIPADO: 'Antecipado',
        }
        return labels.get(obj.modo_atendimento_estoque, obj.modo_atendimento_estoque or '')

    def get_origem_comercial_travada(self, obj):
        return origem_comercial_travada(obj)

    def get_dados_complementares_editaveis(self, obj):
        return dados_complementares_editaveis(obj)

    def get_itens_comerciais_editaveis(self, obj):
        return itens_comerciais_editaveis(obj)

    def get_transportadora_nome(self, obj):
        if obj.transportadora_id and obj.transportadora:
            return obj.transportadora.razao_social
        return ''

    def get_status_conferencia_display(self, obj):
        from apps.fiscal.nfe_saida_prontidao import status_conferencia_display

        return status_conferencia_display(obj.status_conferencia)

    def _cliente_pedido_vinculado(self, nf: NFeSaida):
        pedido = nf.pedido_venda
        if not pedido or not pedido.cliente_id:
            return None
        return pedido.cliente_id

    def _validar_cliente_origem_comercial(self, nf: NFeSaida, cliente) -> None:
        if not nf.faturamento_pedido_venda_id and not nf.pedido_venda_id:
            return
        esperado = self._cliente_pedido_vinculado(nf)
        if esperado is None:
            return
        if cliente and cliente.pk != esperado:
            raise serializers.ValidationError(
                {
                    'cliente_id': (
                        'Cliente não pode ser alterado em NF-e originada de pedido/faturamento. '
                        'Use o cliente do pedido de venda vinculado.'
                    ),
                },
            )

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        cliente = attrs.get('cliente', instance.cliente if instance else None)
        nf_ctx = instance or NFeSaida(
            pedido_venda=attrs.get('pedido_venda'),
            faturamento_pedido_venda=attrs.get('faturamento_pedido_venda'),
        )
        if instance:
            nf_ctx = instance
            if 'pedido_venda' in attrs:
                nf_ctx.pedido_venda = attrs['pedido_venda']
            if 'faturamento_pedido_venda' in attrs:
                nf_ctx.faturamento_pedido_venda = attrs['faturamento_pedido_venda']
        self._validar_cliente_origem_comercial(nf_ctx, cliente)
        if instance and origem_comercial_travada(instance):
            self._validar_itens_origem_comercial_travada()
        if instance and not dados_complementares_editaveis(instance):
            for campo in CAMPOS_COMPLEMENTARES_NFE:
                if campo in attrs:
                    raise serializers.ValidationError(
                        {campo: MSG_DADOS_COMPLEMENTARES_BLOQUEADOS},
                    )
        return super().validate(attrs)

    def get_resumo_atendimento_estoque(self, obj):
        if obj.modo_atendimento_estoque != NFeSaida.ModoAtendimentoEstoque.ANTECIPADO:
            return None
        return montar_resumo_atendimento_estoque_nf(obj)

    def _modo_antecipado(self, modo: str | None) -> bool:
        return (modo or NFeSaida.ModoAtendimentoEstoque.IMEDIATO) == NFeSaida.ModoAtendimentoEstoque.ANTECIPADO

    _STATUS_NFE_EMITIDA = frozenset({'EMITIDA', 'EMITIDO', 'AUTORIZADA_INTERNA', 'AUTORIZADA'})
    _STATUS_NFE_CANCELADA = frozenset({'CANCELADA', 'CANCELADO', 'CANCELADA_INTERNA'})

    @staticmethod
    def _status_nf_normalizado(status: str | None) -> str:
        return (status or '').strip().upper()

    def _status_nf_apos_update(self, instance: NFeSaida, validated_data: dict) -> str:
        if 'status' in validated_data:
            return self._status_nf_normalizado(validated_data['status'])
        return self._status_nf_normalizado(instance.status)

    @staticmethod
    def _nf_ja_finalizada_operacionalmente(instance: NFeSaida) -> bool:
        return nf_ja_finalizada_operacionalmente(instance)

    @staticmethod
    def _item_sem_id(item: dict) -> dict:
        return {k: v for k, v in item.items() if k != 'id'}

    def _validar_itens_origem_comercial_travada(self) -> None:
        raw_itens = (self.initial_data or {}).get('itens')
        if raw_itens is None:
            return
        bloqueados = {'produto', 'produto_id', 'quantidade', 'valor', 'corrida', 'corrida_id'}
        for row in raw_itens:
            if not isinstance(row, dict):
                continue
            if any(k in row for k in bloqueados):
                raise serializers.ValidationError({'itens': MSG_ITENS_ORIGEM_COMERCIAL})
            if row.get('id') in (None, ''):
                raise serializers.ValidationError(
                    {
                        'itens': (
                            'NF-e de faturamento permite alterar apenas complementos de itens '
                            'existentes (informe o id de cada item).'
                        ),
                    },
                )

    def _item_ids_from_initial(self) -> list[int | None]:
        raw_itens = (self.initial_data or {}).get('itens') or []
        ids: list[int | None] = []
        for row in raw_itens:
            if not isinstance(row, dict):
                ids.append(None)
                continue
            raw_id = row.get('id')
            if raw_id in (None, ''):
                ids.append(None)
            else:
                try:
                    ids.append(int(raw_id))
                except (TypeError, ValueError):
                    ids.append(None)
        return ids

    def _sincronizar_itens_complementares(self, nf: NFeSaida, itens_data: list[dict]) -> None:
        """NF-e de faturamento: só campos de pedido do cliente / observação por item."""
        bloqueados = {'produto', 'produto_id', 'quantidade', 'valor', 'corrida', 'corrida_id'}
        existentes = {it.id: it for it in nf.itens.all()}
        for row in itens_data:
            if not isinstance(row, dict):
                continue
            if any(k in row for k in bloqueados):
                raise ValidationError({'itens': MSG_ITENS_ORIGEM_COMERCIAL})
            raw_id = row.get('id')
            if raw_id in (None, ''):
                raise ValidationError(
                    {
                        'itens': (
                            'NF-e de faturamento permite alterar apenas complementos de itens '
                            'existentes (informe o id de cada item).'
                        ),
                    },
                )
            try:
                pk = int(raw_id)
            except (TypeError, ValueError):
                continue
            item = existentes.get(pk)
            if item is None:
                continue
            update_fields = []
            for field in CAMPOS_COMPLEMENTARES_ITEM_NFE:
                if field in row:
                    setattr(item, field, row.get(field) or '')
                    update_fields.append(field)
            if update_fields:
                item.save(update_fields=update_fields)

    def _persist_itens_imediato(self, nf: NFeSaida, itens_data: list[dict]) -> None:
        nf.itens.all().delete()
        for item in itens_data:
            ItemNFeSaida.objects.create(nf=nf, **self._item_sem_id(item))

    def _persist_itens_antecipado(self, nf: NFeSaida, itens_data: list[dict]) -> None:
        sync_itens_nf_saida_antecipada(
            nf,
            [self._item_sem_id(item) for item in itens_data],
            item_ids_payload=self._item_ids_from_initial(),
        )

    def _aplicar_estoque_saida(self, nf: NFeSaida) -> None:
        if self._modo_antecipado(nf.modo_atendimento_estoque):
            return
        try:
            aplicar_todos_itens_saida(nf)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc

    def _finalizar_nf_saida(self, nf: NFeSaida) -> None:
        recalcular_valor_nf_saida(nf)
        sincronizar_financeiro_nf_saida(nf)
        nf.save(
            update_fields=[
                'valor_total',
                'condicao_pagamento_texto',
                'dias_parcelas',
                'quantidade_parcelas',
                'vencimentos_finais',
                'titulos_receber',
            ],
        )
        self._aplicar_estoque_saida(nf)
        _gerar_ou_atualizar_certificado(nf)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cliente_id'] = instance.cliente_id
        data['data'] = instance.data.isoformat()
        data['valor_total'] = float(instance.valor_total)
        data['vencimentos_finais'] = [d.isoformat() for d in instance.vencimentos_finais]
        data['pedido_venda_id'] = instance.pedido_venda_id
        data['faturamento_pedido_venda_id'] = instance.faturamento_pedido_venda_id
        data['transportadora_id'] = instance.transportadora_id
        data['valor_frete'] = float(instance.valor_frete)
        data['peso_bruto'] = float(instance.peso_bruto)
        data['peso_liquido'] = float(instance.peso_liquido)
        return data

    def _finalizar_nf_saida_rascunho(self, nf: NFeSaida) -> None:
        """Rascunho: só totais — sem estoque, financeiro ou certificado."""
        recalcular_valor_nf_saida(nf)

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        modo = validated_data.get(
            'modo_atendimento_estoque',
            NFeSaida.ModoAtendimentoEstoque.IMEDIATO,
        )
        status_nf = (validated_data.get('status') or '').strip().upper()
        nf = NFeSaida.objects.create(**validated_data)
        if self._modo_antecipado(modo):
            for item in itens_data:
                row = ItemNFeSaida.objects.create(nf=nf, **self._item_sem_id(item))
                criar_ou_atualizar_atendimento_item_antecipado(row)
        else:
            for item in itens_data:
                ItemNFeSaida.objects.create(nf=nf, **self._item_sem_id(item))
        try:
            if status_nf == 'RASCUNHO':
                self._finalizar_nf_saida_rascunho(nf)
            else:
                self._finalizar_nf_saida(nf)
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return nf

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.faturamento_pedido_venda_id or instance.pedido_venda_id:
            validated_data.pop('cliente', None)

        status_nf = self._status_nf_apos_update(instance, validated_data)
        ja_finalizada = self._nf_ja_finalizada_operacionalmente(instance)
        if ja_finalizada and status_nf in self._STATUS_NFE_CANCELADA:
            raise ValidationError({'detail': 'NF-e cancelada não pode ser alterada.'})

        itens_data = validated_data.pop('itens', None)
        alterou_conferencia = itens_data is not None or any(
            k in validated_data for k in CAMPOS_COMPLEMENTARES_NFE
        )
        if origem_comercial_travada(instance) and itens_data is not None:
            self._sincronizar_itens_complementares(instance, itens_data)
            itens_data = None
        if ja_finalizada and itens_data is not None:
            raise ValidationError(
                {'itens': 'NF-e emitida ou autorizada não permite alteração de itens.'},
            )
        if ja_finalizada:
            for campo in list(validated_data.keys()):
                if campo in CAMPOS_COMPLEMENTARES_NFE:
                    validated_data.pop(campo)

        novo_modo = validated_data.get('modo_atendimento_estoque', instance.modo_atendimento_estoque)
        try:
            validar_troca_modo_atendimento(instance, novo_modo)
        except ValueError as exc:
            raise ValidationError({'modo_atendimento_estoque': str(exc)}) from exc

        reverter_estoque = (
            not ja_finalizada
            and status_nf == 'RASCUNHO'
            and instance.modo_atendimento_estoque == NFeSaida.ModoAtendimentoEstoque.IMEDIATO
        )
        if reverter_estoque:
            reverter_todos_itens_saida(instance)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if itens_data is not None:
            if self._modo_antecipado(novo_modo):
                try:
                    self._persist_itens_antecipado(instance, itens_data)
                except ValueError as exc:
                    raise ValidationError({'itens': str(exc)}) from exc
            else:
                self._persist_itens_imediato(instance, itens_data)

        try:
            if status_nf == 'RASCUNHO':
                self._finalizar_nf_saida_rascunho(instance)
            elif ja_finalizada:
                pass
            else:
                self._finalizar_nf_saida(instance)
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)}) from exc

        if alterou_conferencia and dados_complementares_editaveis(instance):
            from apps.fiscal.nfe_saida_prontidao import processar_prontidao_apos_salvar_conferencia

            request = self.context.get('request')
            usuario = getattr(request, 'user', None) if request else None
            processar_prontidao_apos_salvar_conferencia(
                instance,
                usuario=usuario,
                alterou_dados=alterou_conferencia,
            )

        return instance


class ItemNFeSaidaHistoricaImportadaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemNFeSaidaHistoricaImportada
        fields = ('id', 'n_item', 'prod_json', 'imposto_json')


class ItemNFeEntradaHistoricaImportadaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemNFeEntradaHistoricaImportada
        fields = ('id', 'n_item', 'prod_json', 'imposto_json')


class NFeEntradaHistoricaImportadaListSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.SerializerMethodField(read_only=True)
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    empresa_id = serializers.SerializerMethodField(read_only=True)
    papel_empresa = serializers.SerializerMethodField(read_only=True)
    fornecedor_cnpj = serializers.SerializerMethodField(read_only=True)
    fornecedor_id = serializers.SerializerMethodField(read_only=True)
    conferencia_status = serializers.SerializerMethodField(read_only=True)
    conferencia_preparado_em = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NFeEntradaHistoricaImportada
        fields = (
            'id',
            'chave_acesso',
            'numero',
            'serie',
            'dh_emissao',
            'valor_total_nf',
            'valor_produtos',
            'v_frete',
            'v_desc',
            'nat_op',
            'cstat',
            'protocolo',
            'empresa_destinataria',
            'empresa_id',
            'empresa_nome',
            'fornecedor_emitente',
            'fornecedor_id',
            'fornecedor_nome',
            'fornecedor_cnpj',
            'emit_json',
            'papel_empresa',
            'papel_empresa_no_documento',
            'nome_arquivo',
            'importado_em',
            'importada',
            'origem_externa',
            'historica',
            'conferencia_status',
            'conferencia_preparado_em',
        )

    def get_empresa_id(self, obj):
        return obj.empresa_destinataria_id

    def get_empresa_nome(self, obj):
        return obj.empresa_destinataria.razao_social if obj.empresa_destinataria_id else ''

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor_emitente.razao_social if obj.fornecedor_emitente_id else (obj.emit_json or {}).get('xNome', '')

    def get_fornecedor_cnpj(self, obj):
        if obj.fornecedor_emitente_id:
            return obj.fornecedor_emitente.cnpj
        return (obj.emit_json or {}).get('CNPJ', '')

    def get_fornecedor_id(self, obj):
        return obj.fornecedor_emitente_id

    def get_papel_empresa(self, obj):
        return obj.papel_empresa_no_documento or ('destinatario' if obj.empresa_destinataria_id else '')

    def get_conferencia_status(self, obj):
        try:
            return obj.conferencia.status
        except ObjectDoesNotExist:
            return None

    def get_conferencia_preparado_em(self, obj):
        try:
            c = obj.conferencia
        except ObjectDoesNotExist:
            return None
        return c.preparado_em.isoformat() if c.preparado_em else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['valor_total_nf'] = float(instance.valor_total_nf)
        data['valor_produtos'] = float(instance.valor_produtos)
        data['v_frete'] = float(instance.v_frete)
        data['v_desc'] = float(instance.v_desc)
        data['dh_emissao'] = instance.dh_emissao.isoformat() if instance.dh_emissao else None
        data['importado_em'] = instance.importado_em.isoformat() if instance.importado_em else None
        return data


class NFeEntradaHistoricaImportadaSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.SerializerMethodField(read_only=True)
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    empresa_id = serializers.SerializerMethodField(read_only=True)
    papel_empresa = serializers.SerializerMethodField(read_only=True)
    itens = ItemNFeEntradaHistoricaImportadaSerializer(many=True, read_only=True)

    class Meta:
        model = NFeEntradaHistoricaImportada
        fields = (
            'id',
            'chave_acesso',
            'numero',
            'serie',
            'modelo',
            'dh_emissao',
            'tp_amb',
            'tp_nf',
            'nat_op',
            'versao_layout',
            'cstat',
            'xmotivo',
            'protocolo',
            'valor_produtos',
            'valor_total_nf',
            'v_frete',
            'v_seg',
            'v_desc',
            'v_outro',
            'emit_json',
            'dest_json',
            'totais_json',
            'reforma_e_outros_json',
            'prot_json',
            'empresa_destinataria',
            'empresa_id',
            'empresa_nome',
            'fornecedor_emitente',
            'fornecedor_nome',
            'papel_empresa',
            'papel_empresa_no_documento',
            'importada',
            'origem_externa',
            'historica',
            'nome_arquivo',
            'importado_em',
            'itens',
        )

    def get_empresa_id(self, obj):
        return obj.empresa_destinataria_id

    def get_empresa_nome(self, obj):
        return obj.empresa_destinataria.razao_social if obj.empresa_destinataria_id else ''

    def get_fornecedor_nome(self, obj):
        return obj.fornecedor_emitente.razao_social if obj.fornecedor_emitente_id else (obj.emit_json or {}).get('xNome', '')

    def get_papel_empresa(self, obj):
        return obj.papel_empresa_no_documento or ('destinatario' if obj.empresa_destinataria_id else '')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('valor_produtos', 'valor_total_nf', 'v_frete', 'v_seg', 'v_desc', 'v_outro'):
            if k in data and data[k] is not None:
                data[k] = float(data[k])
        data['dh_emissao'] = instance.dh_emissao.isoformat() if instance.dh_emissao else None
        data['importado_em'] = instance.importado_em.isoformat() if instance.importado_em else None
        return data


class ItemNFeEntradaConferenciaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
        allow_null=True,
        required=False,
    )
    item_pedido_compra_id = serializers.PrimaryKeyRelatedField(
        queryset=ItemPedidoCompra.objects.select_related('pedido').all(),
        source='item_pedido_compra',
        allow_null=True,
        required=False,
    )
    produto_nome = serializers.SerializerMethodField(read_only=True)
    sugestoes_produto = serializers.SerializerMethodField(read_only=True)
    sugestoes_item_pedido = serializers.SerializerMethodField(read_only=True)
    dados_nf = serializers.SerializerMethodField(read_only=True)
    item_pedido_resumo = serializers.SerializerMethodField(read_only=True)
    pedido_numero = serializers.SerializerMethodField(read_only=True)
    item_pedido_produto_codigo = serializers.SerializerMethodField(read_only=True)
    item_pedido_produto_descricao = serializers.SerializerMethodField(read_only=True)
    item_pedido_quantidade = serializers.SerializerMethodField(read_only=True)
    item_pedido_unidade = serializers.SerializerMethodField(read_only=True)
    item_pedido_valor_unitario = serializers.SerializerMethodField(read_only=True)
    tributos_nf = serializers.SerializerMethodField(read_only=True)
    resultado_fiscal = serializers.SerializerMethodField(read_only=True)
    elegibilidade_estoque = serializers.SerializerMethodField(read_only=True)
    quantidade_alocada_atendimento = serializers.SerializerMethodField(read_only=True)
    quantidade_disponivel_atendimento = serializers.SerializerMethodField(read_only=True)
    vinculos_atendimento = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ItemNFeEntradaConferencia
        fields = (
            'id',
            'item_nfe_historico',
            'produto_id',
            'produto_nome',
            'item_pedido_compra_id',
            'item_pedido_resumo',
            'pedido_numero',
            'item_pedido_produto_codigo',
            'item_pedido_produto_descricao',
            'item_pedido_quantidade',
            'item_pedido_unidade',
            'item_pedido_valor_unitario',
            'status',
            'motivo_ignorado',
            'observacao',
            'corrida',
            'lote',
            'rastreabilidade_observacao',
            'unidade_nf',
            'quantidade_nf',
            'valor_unitario_nf',
            'valor_total_nf',
            'unidade_estoque_calculada',
            'quantidade_estoque_calculada',
            'peso_total_kg',
            'metros_total',
            'barras_total',
            'toneladas_total',
            'divergencias',
            'alertas',
            'snapshot_produto',
            'snapshot_pedido',
            'sugestoes_produto',
            'sugestoes_item_pedido',
            'dados_nf',
            'tributos_nf',
            'resultado_fiscal',
            'elegibilidade_estoque',
            'quantidade_alocada_atendimento',
            'quantidade_disponivel_atendimento',
            'vinculos_atendimento',
        )
        read_only_fields = (
            'sugestoes_item_pedido',
            'item_pedido_resumo',
            'pedido_numero',
            'item_pedido_produto_codigo',
            'item_pedido_produto_descricao',
            'item_pedido_quantidade',
            'item_pedido_unidade',
            'item_pedido_valor_unitario',
            'tributos_nf',
            'resultado_fiscal',
            'elegibilidade_estoque',
            'quantidade_alocada_atendimento',
            'quantidade_disponivel_atendimento',
            'vinculos_atendimento',
        )

    def get_quantidade_alocada_atendimento(self, obj: ItemNFeEntradaConferencia) -> str:
        return f'{quantidade_alocada_item_conferencia(obj):.3f}'

    def get_quantidade_disponivel_atendimento(self, obj: ItemNFeEntradaConferencia) -> str:
        return f'{quantidade_disponivel_item_conferencia(obj):.3f}'

    def get_vinculos_atendimento(self, obj: ItemNFeEntradaConferencia) -> list:
        return listar_vinculos_item_conferencia(obj)

    def get_tributos_nf(self, obj: ItemNFeEntradaConferencia) -> dict:
        from apps.fiscal.services.imposto_item_xml import extrair_tributos_item

        prod_json = obj.item_nfe_historico.prod_json or {}
        imposto_json = obj.item_nfe_historico.imposto_json or {}
        trib = extrair_tributos_item(prod_json, imposto_json)
        from apps.regras_fiscais.entrada_fiscal import _montar_impostos_nf

        snap = _montar_impostos_nf(trib)
        return {
            'cst_icms': snap.get('cst_icms') or trib.get('cst_icms') or '',
            'csosn': snap.get('csosn') or trib.get('cst_icms_detalhe') or '',
            'cst_pis': snap.get('cst_pis') or trib.get('cst_pis') or '',
            'cst_cofins': snap.get('cst_cofins') or trib.get('cst_cofins') or '',
            'cst_ipi': snap.get('cst_ipi') or trib.get('cst_ipi') or '',
            'aliquota_icms': snap.get('aliquota_icms') or '',
            'aliquota_ipi': snap.get('aliquota_ipi') or '',
            'aliquota_pis': snap.get('aliquota_pis') or '',
            'aliquota_cofins': snap.get('aliquota_cofins') or '',
        }

    def get_resultado_fiscal(self, obj: ItemNFeEntradaConferencia) -> dict:
        contexto = self.context.get('contexto_fiscal_entrada')
        regras = self.context.get('regras_fiscais_entrada')
        if contexto is None or regras is None:
            conferencia = self.context.get('conferencia')
            if conferencia is None:
                conferencia = obj.conferencia
            if contexto is None:
                contexto = montar_contexto_fiscal_entrada(conferencia)
            if regras is None:
                from apps.regras_fiscais.entrada_fiscal import carregar_regras_fiscais_entrada_ativas

                regras = carregar_regras_fiscais_entrada_ativas()
        return avaliar_item_entrada_fiscal(obj, contexto, regras)

    def get_elegibilidade_estoque(self, obj: ItemNFeEntradaConferencia) -> dict:
        cert_map = self.context.get('certificados_fornecedor_por_item') or {}
        cert_info = cert_map.get(obj.id, {})
        divergencias_aceitas = bool(self.context.get('divergencias_aceitas_conferencia'))
        return avaliar_elegibilidade_estoque_item_conferencia(
            obj,
            resultado_fiscal=self.get_resultado_fiscal(obj),
            divergencias_aceitas=divergencias_aceitas,
            certificado_fornecedor_info=cert_info,
        )

    def _resumo_pedido(self, obj: ItemNFeEntradaConferencia) -> dict | None:
        return item_pedido_resumo_dict(obj)

    def get_item_pedido_resumo(self, obj: ItemNFeEntradaConferencia):
        return self._resumo_pedido(obj)

    def get_pedido_numero(self, obj: ItemNFeEntradaConferencia) -> str:
        resumo = self._resumo_pedido(obj)
        return resumo.get('pedido_numero', '') if resumo else ''

    def get_item_pedido_produto_codigo(self, obj: ItemNFeEntradaConferencia) -> str:
        resumo = self._resumo_pedido(obj)
        return resumo.get('codigo', '') if resumo else ''

    def get_item_pedido_produto_descricao(self, obj: ItemNFeEntradaConferencia) -> str:
        resumo = self._resumo_pedido(obj)
        return resumo.get('descricao', '') if resumo else ''

    def get_item_pedido_quantidade(self, obj: ItemNFeEntradaConferencia) -> str:
        resumo = self._resumo_pedido(obj)
        return str(resumo.get('quantidade', '')) if resumo else ''

    def get_item_pedido_unidade(self, obj: ItemNFeEntradaConferencia) -> str:
        resumo = self._resumo_pedido(obj)
        return resumo.get('unidade', '') if resumo else ''

    def get_item_pedido_valor_unitario(self, obj: ItemNFeEntradaConferencia) -> str:
        resumo = self._resumo_pedido(obj)
        return str(resumo.get('valor_unitario', '')) if resumo else ''

    def get_produto_nome(self, obj):
        return obj.produto.descricao if obj.produto_id else ''

    def get_dados_nf(self, obj):
        return _extract_prod_fields(obj.item_nfe_historico.prod_json or {})

    def get_sugestoes_item_pedido(self, obj: ItemNFeEntradaConferencia) -> list[dict]:
        if not self.context.get('pedido_compra_id'):
            return []
        itens_pedido = self.context.get('itens_pedido') or []
        if not itens_pedido:
            return []
        vinculados = set(self.context.get('conferencia_itens_vinculos') or [])
        vinculados_outras = {vid for vid in vinculados if vid != obj.item_pedido_compra_id}
        return sugerir_itens_pedido_linha(
            obj,
            itens_pedido,
            vinculados_outras_linhas=vinculados_outras,
        )

    def get_sugestoes_produto(self, obj):
        prod = obj.item_nfe_historico.prod_json or {}
        codigo = str(prod.get('cProd') or '').strip()
        descricao = str(prod.get('xProd') or '').strip()
        ncm = str(prod.get('NCM') or '').strip()
        qs = Produto.objects.all()
        score_map: dict[int, int] = {}
        if codigo:
            for p in qs.filter(codigo_completo__icontains=codigo)[:5]:
                score_map[p.id] = score_map.get(p.id, 0) + 4
        if descricao:
            for p in qs.filter(descricao__icontains=descricao[:32])[:10]:
                score_map[p.id] = score_map.get(p.id, 0) + 3
        if ncm:
            for p in qs.filter(ncm__icontains=ncm)[:10]:
                score_map[p.id] = score_map.get(p.id, 0) + 2
        if not score_map:
            return []
        produtos = {p.id: p for p in Produto.objects.filter(id__in=list(score_map.keys()))}
        ranked = sorted(score_map.items(), key=lambda x: (-x[1], x[0]))[:5]
        return [
            {'id': pid, 'codigo': produtos[pid].codigo_completo, 'descricao': produtos[pid].descricao, 'score': score}
            for pid, score in ranked
            if pid in produtos
        ]

    def validate(self, attrs):
        normalize_operational_fields(
            attrs,
            {
                'status',
                'motivo_ignorado',
                'observacao',
                'corrida',
                'lote',
                'rastreabilidade_observacao',
                'unidade_nf',
                'unidade_estoque_calculada',
            },
        )
        produto = attrs.get('produto', getattr(self.instance, 'produto', None))
        status = attrs.get('status', getattr(self.instance, 'status', ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO))
        corrida = attrs.get('corrida', getattr(self.instance, 'corrida', ''))
        quantidade_estoque = attrs.get(
            'quantidade_estoque_calculada',
            getattr(self.instance, 'quantidade_estoque_calculada', Decimal('0')),
        )
        motivo_ignorado = attrs.get('motivo_ignorado', getattr(self.instance, 'motivo_ignorado', ''))
        if status in {ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO, ItemNFeEntradaConferencia.Status.CONFERIDO} and not produto:
            raise serializers.ValidationError(
                {'produto_id': 'Produto cadastrado no NEXUS APP é obrigatório para este status.'}
            )
        if status == ItemNFeEntradaConferencia.Status.CONFERIDO:
            if quantidade_estoque <= 0:
                raise serializers.ValidationError(
                    {'quantidade_estoque_calculada': 'Quantidade de estoque calculada deve ser maior que zero.'}
                )
            if produto and produto.get_tipo_controle_unidade_efetivo() in {'DIMENSIONAL', 'TUBO', 'BARRA', 'PERFIL'} and not corrida:
                raise serializers.ValidationError({'corrida': 'Corrida é obrigatória para produto com rastreabilidade.'})
        if status == ItemNFeEntradaConferencia.Status.IGNORADO and not motivo_ignorado.strip():
            raise serializers.ValidationError({'motivo_ignorado': 'Informe o motivo para ignorar o item.'})
        if produto:
            attrs['snapshot_produto'] = build_produto_snapshot(produto)

        item_pedido_in_payload = 'item_pedido_compra' in attrs
        item_pedido = attrs.get('item_pedido_compra') if item_pedido_in_payload else None
        if item_pedido_in_payload and item_pedido is None:
            attrs['snapshot_pedido'] = {}
        elif item_pedido is not None:
            pedido_compra_id = self.context.get('pedido_compra_id')
            if not pedido_compra_id:
                raise serializers.ValidationError(
                    {
                        'item_pedido_compra_id': (
                            'Selecione o pedido de compra no cabeçalho antes de vincular itens do pedido.'
                        ),
                    },
                )
            if item_pedido.pedido_id != pedido_compra_id:
                raise serializers.ValidationError(
                    {
                        'item_pedido_compra_id': (
                            'O item do pedido não pertence ao pedido de compra vinculado à conferência.'
                        ),
                    },
                )
            attrs['snapshot_pedido'] = build_snapshot_pedido(item_pedido)

        return attrs


class NFeEntradaConferenciaSerializer(serializers.ModelSerializer):
    pedido_compra_id = serializers.PrimaryKeyRelatedField(
        queryset=PedidoCompra.objects.all(),
        source='pedido_compra',
        allow_null=True,
        required=False,
    )
    itens = ItemNFeEntradaConferenciaSerializer(many=True, required=False)
    fornecedor_nome = serializers.SerializerMethodField(read_only=True)
    fornecedor_cnpj = serializers.SerializerMethodField(read_only=True)
    numero = serializers.SerializerMethodField(read_only=True)
    serie = serializers.SerializerMethodField(read_only=True)
    data_emissao = serializers.SerializerMethodField(read_only=True)
    valor_total = serializers.SerializerMethodField(read_only=True)
    pedido_compra_numero = serializers.SerializerMethodField(read_only=True)
    resumo_pedido = serializers.SerializerMethodField(read_only=True)
    resumo_fiscal = serializers.SerializerMethodField(read_only=True)
    resumo_elegibilidade_estoque = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NFeEntradaConferencia
        fields = (
            'id',
            'nf_entrada_historica',
            'numero',
            'serie',
            'data_emissao',
            'valor_total',
            'fornecedor_nome',
            'fornecedor_cnpj',
            'pedido_compra_id',
            'pedido_compra_numero',
            'resumo_pedido',
            'resumo_fiscal',
            'resumo_elegibilidade_estoque',
            'status',
            'divergencias_aceitas',
            'observacao_divergencias',
            'preparado_em',
            'estoque_aplicado_em',
            'estoque_aplicado_observacao',
            'itens',
        )

    def get_fornecedor_nome(self, obj):
        nf = obj.nf_entrada_historica
        return nf.fornecedor_emitente.razao_social if nf.fornecedor_emitente_id else (nf.emit_json or {}).get('xNome', '')

    def get_fornecedor_cnpj(self, obj):
        nf = obj.nf_entrada_historica
        return nf.fornecedor_emitente.cnpj if nf.fornecedor_emitente_id else (nf.emit_json or {}).get('CNPJ', '')

    def get_numero(self, obj):
        return obj.nf_entrada_historica.numero

    def get_serie(self, obj):
        return obj.nf_entrada_historica.serie

    def get_data_emissao(self, obj):
        nf = obj.nf_entrada_historica
        return nf.dh_emissao.isoformat() if nf.dh_emissao else None

    def get_valor_total(self, obj):
        return float(obj.nf_entrada_historica.valor_total_nf)

    def get_pedido_compra_numero(self, obj):
        return obj.pedido_compra.numero if obj.pedido_compra_id else ''

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'status', 'observacao_divergencias'})
        return attrs

    def _inject_fiscal_entrada_context(self, conferencia: NFeEntradaConferencia) -> None:
        from apps.regras_fiscais.entrada_fiscal import carregar_regras_fiscais_entrada_ativas

        contexto = montar_contexto_fiscal_entrada(conferencia)
        regras = carregar_regras_fiscais_entrada_ativas()
        item_field = self.fields['itens']
        item_serializer = item_field.child if hasattr(item_field, 'child') else item_field
        item_serializer.context['conferencia'] = conferencia
        item_serializer.context['contexto_fiscal_entrada'] = contexto
        item_serializer.context['regras_fiscais_entrada'] = regras
        self._contexto_fiscal_entrada = contexto
        self._regras_fiscais_entrada = regras

    def _inject_elegibilidade_estoque_context(self, conferencia: NFeEntradaConferencia) -> None:
        item_ids = [it.id for it in conferencia.itens.all()]
        cert_map = carregar_certificados_fornecedor_por_item_conferencia(item_ids)
        item_field = self.fields['itens']
        item_serializer = item_field.child if hasattr(item_field, 'child') else item_field
        item_serializer.context['certificados_fornecedor_por_item'] = cert_map
        item_serializer.context['divergencias_aceitas_conferencia'] = conferencia.divergencias_aceitas
        self._certificados_fornecedor_por_item = cert_map
        self._divergencias_aceitas_conferencia = conferencia.divergencias_aceitas

    def _inject_itens_pedido_context(self, conferencia: NFeEntradaConferencia) -> None:
        pedido_id = conferencia.pedido_compra_id
        itens_pedido: list[ItemPedidoCompra] = []
        if pedido_id:
            prefetched = getattr(conferencia.pedido_compra, 'itens', None) if conferencia.pedido_compra_id else None
            if prefetched is not None and hasattr(prefetched, 'all'):
                itens_pedido = list(prefetched.all())
            else:
                itens_pedido = list(
                    ItemPedidoCompra.objects.filter(pedido_id=pedido_id).select_related('produto'),
                )
        vinculados = {
            it.item_pedido_compra_id
            for it in conferencia.itens.all()
            if it.item_pedido_compra_id
        }
        item_field = self.fields['itens']
        item_serializer = item_field.child if hasattr(item_field, 'child') else item_field
        item_serializer.context['pedido_compra_id'] = pedido_id
        item_serializer.context['itens_pedido'] = itens_pedido
        item_serializer.context['conferencia_itens_vinculos'] = vinculados
        self._itens_pedido_cache = itens_pedido

    def get_resumo_pedido(self, obj: NFeEntradaConferencia) -> dict:
        return montar_resumo_pedido_conferencia(
            obj,
            getattr(self, '_itens_pedido_cache', None),
        )

    def get_resumo_fiscal(self, obj: NFeEntradaConferencia) -> dict:
        if hasattr(self, '_resumo_fiscal_cache'):
            return self._resumo_fiscal_cache
        contexto = getattr(self, '_contexto_fiscal_entrada', None) or montar_contexto_fiscal_entrada(obj)
        regras = getattr(self, '_regras_fiscais_entrada', None)
        if regras is None:
            from apps.regras_fiscais.entrada_fiscal import carregar_regras_fiscais_entrada_ativas

            regras = carregar_regras_fiscais_entrada_ativas()
        linhas = list(obj.itens.select_related('item_nfe_historico', 'produto').all())
        ignorados = sum(1 for linha in linhas if linha.status == linha.Status.IGNORADO)
        resultados = [
            avaliar_item_entrada_fiscal(linha, contexto, regras)
            for linha in linhas
            if linha.status != linha.Status.IGNORADO
        ]
        return montar_resumo_fiscal_conferencia(
            resultados,
            contexto,
            linhas_ignoradas=ignorados,
        )

    def get_resumo_elegibilidade_estoque(self, obj: NFeEntradaConferencia) -> dict:
        if hasattr(self, '_resumo_elegibilidade_cache'):
            return self._resumo_elegibilidade_cache
        return {'aptos': 0, 'aptos_com_alerta': 0, 'bloqueados': 0, 'nao_movimentam': 0}

    def to_representation(self, instance):
        self._inject_fiscal_entrada_context(instance)
        self._inject_elegibilidade_estoque_context(instance)
        self._inject_itens_pedido_context(instance)
        self._resumo_fiscal_cache = self.get_resumo_fiscal(instance)
        data = super().to_representation(instance)
        data['pedido_compra_id'] = instance.pedido_compra_id
        data['preparado_em'] = instance.preparado_em.isoformat() if instance.preparado_em else None
        data['estoque_aplicado_em'] = (
            instance.estoque_aplicado_em.isoformat() if instance.estoque_aplicado_em else None
        )
        elegibilidades = [
            (row.get('elegibilidade_estoque') or {})
            for row in (data.get('itens') or [])
        ]
        data['resumo_elegibilidade_estoque'] = montar_resumo_elegibilidade_estoque(elegibilidades)
        self._resumo_elegibilidade_cache = data['resumo_elegibilidade_estoque']
        return data

class EventoNFeSaidaHistoricaImportadaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoNFeSaidaHistoricaImportada
        fields = (
            'id',
            'chave_acesso',
            'tipo_evento',
            'protocolo_evento',
            'id_evento',
            'sequencial_evento',
            'data_evento',
            'evento_json',
            'nome_arquivo',
            'importado_em',
        )


class EventoNFeSaidaHistoricaPendenteSerializer(serializers.ModelSerializer):
    data_evento = serializers.SerializerMethodField()

    class Meta:
        model = EventoNFeSaidaHistoricaPendente
        fields = (
            'id',
            'chave_nfe',
            'tipo_evento',
            'descricao_evento',
            'sequencia_evento',
            'data_evento',
            'protocolo_evento',
            'id_evento',
            'justificativa',
            'nome_arquivo',
            'direcao',
            'status',
            'mensagem',
            'nf',
            'criado_em',
            'atualizado_em',
        )

    def get_data_evento(self, obj):
        return obj.data_evento.isoformat() if obj.data_evento else None


class NFeSaidaHistoricaImportadaListSerializer(serializers.ModelSerializer):
    empresa_emitente_nome = serializers.SerializerMethodField(read_only=True)
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    icms_valor_lido_xml = serializers.SerializerMethodField(read_only=True)
    tem_reforma_e_outros_json = serializers.SerializerMethodField(read_only=True)
    sem_bloco_icmstot = serializers.SerializerMethodField(read_only=True)
    status_visual = serializers.SerializerMethodField(read_only=True)
    cstat_visual = serializers.SerializerMethodField(read_only=True)
    motivo_visual = serializers.SerializerMethodField(read_only=True)
    protocolo_cancelamento = serializers.SerializerMethodField(read_only=True)
    empresa_id = serializers.SerializerMethodField(read_only=True)
    empresa_nome = serializers.SerializerMethodField(read_only=True)
    papel_empresa = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NFeSaidaHistoricaImportada
        fields = (
            'id',
            'chave_acesso',
            'numero',
            'serie',
            'dh_emissao',
            'valor_total_nf',
            'valor_produtos',
            'v_frete',
            'v_desc',
            'nat_op',
            'cstat',
            'protocolo',
            'empresa_emitente',
            'empresa_emitente_nome',
            'cliente',
            'cliente_nome',
            'icms_valor_lido_xml',
            'tem_reforma_e_outros_json',
            'sem_bloco_icmstot',
            'nome_arquivo',
            'importado_em',
            'importada',
            'origem_externa',
            'historica',
            'cancelada',
            'status_documento',
            'data_cancelamento',
            'protocolo_evento',
            'tipo_evento',
            'status_visual',
            'cstat_visual',
            'motivo_visual',
            'protocolo_cancelamento',
            'empresa_id',
            'empresa_nome',
            'papel_empresa',
            'papel_empresa_no_documento',
        )

    def get_empresa_emitente_nome(self, obj):
        return obj.empresa_emitente.razao_social if obj.empresa_emitente_id else ''

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social if obj.cliente_id else (obj.dest_json or {}).get('xNome', '')

    def get_icms_valor_lido_xml(self, obj):
        return float(extrair_totais_fiscais_documento(obj.totais_json)['icms_valor'])

    def get_tem_reforma_e_outros_json(self, obj):
        r = obj.reforma_e_outros_json
        return isinstance(r, dict) and len(r) > 0

    def get_sem_bloco_icmstot(self, obj):
        return not documento_tem_icmstot(obj.totais_json)

    def get_status_visual(self, obj):
        return _cancelamento_snapshot(obj)['status_visual']

    def get_cstat_visual(self, obj):
        return _cancelamento_snapshot(obj)['cstat_visual']

    def get_motivo_visual(self, obj):
        return _cancelamento_snapshot(obj)['motivo_visual']

    def get_protocolo_cancelamento(self, obj):
        return _cancelamento_snapshot(obj)['protocolo_cancelamento']

    def get_empresa_id(self, obj):
        return obj.empresa_emitente_id

    def get_empresa_nome(self, obj):
        return obj.empresa_emitente.razao_social if obj.empresa_emitente_id else ''

    def get_papel_empresa(self, obj):
        return obj.papel_empresa_no_documento or ('emitente' if obj.empresa_emitente_id else '')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['valor_total_nf'] = float(instance.valor_total_nf)
        data['valor_produtos'] = float(instance.valor_produtos)
        data['v_frete'] = float(instance.v_frete)
        data['v_desc'] = float(instance.v_desc)
        data['dh_emissao'] = instance.dh_emissao.isoformat() if instance.dh_emissao else None
        data['importado_em'] = instance.importado_em.isoformat() if instance.importado_em else None
        data['data_cancelamento'] = instance.data_cancelamento.isoformat() if instance.data_cancelamento else None
        return data


class NFeSaidaHistoricaImportadaSerializer(serializers.ModelSerializer):
    empresa_emitente_nome = serializers.SerializerMethodField(read_only=True)
    cliente_nome = serializers.SerializerMethodField(read_only=True)
    itens = ItemNFeSaidaHistoricaImportadaSerializer(many=True, read_only=True)
    eventos = EventoNFeSaidaHistoricaImportadaSerializer(many=True, read_only=True)
    status_visual = serializers.SerializerMethodField(read_only=True)
    cstat_visual = serializers.SerializerMethodField(read_only=True)
    motivo_visual = serializers.SerializerMethodField(read_only=True)
    protocolo_cancelamento = serializers.SerializerMethodField(read_only=True)
    empresa_id = serializers.SerializerMethodField(read_only=True)
    empresa_nome = serializers.SerializerMethodField(read_only=True)
    papel_empresa = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NFeSaidaHistoricaImportada
        fields = (
            'id',
            'chave_acesso',
            'numero',
            'serie',
            'modelo',
            'dh_emissao',
            'tp_amb',
            'tp_nf',
            'nat_op',
            'versao_layout',
            'cstat',
            'xmotivo',
            'protocolo',
            'valor_produtos',
            'valor_total_nf',
            'v_frete',
            'v_seg',
            'v_desc',
            'v_outro',
            'emit_json',
            'dest_json',
            'totais_json',
            'reforma_e_outros_json',
            'prot_json',
            'empresa_emitente',
            'empresa_emitente_nome',
            'cliente',
            'cliente_nome',
            'importada',
            'origem_externa',
            'historica',
            'cancelada',
            'status_documento',
            'data_cancelamento',
            'protocolo_evento',
            'tipo_evento',
            'evento_cancelamento_json',
            'evento_cancelamento_id',
            'status_visual',
            'cstat_visual',
            'motivo_visual',
            'protocolo_cancelamento',
            'empresa_id',
            'empresa_nome',
            'papel_empresa',
            'papel_empresa_no_documento',
            'nome_arquivo',
            'importado_em',
            'itens',
            'eventos',
        )

    def get_empresa_emitente_nome(self, obj):
        return obj.empresa_emitente.razao_social if obj.empresa_emitente_id else ''

    def get_cliente_nome(self, obj):
        return obj.cliente.razao_social if obj.cliente_id else (obj.dest_json or {}).get('xNome', '')

    def get_status_visual(self, obj):
        return _cancelamento_snapshot(obj)['status_visual']

    def get_cstat_visual(self, obj):
        return _cancelamento_snapshot(obj)['cstat_visual']

    def get_motivo_visual(self, obj):
        return _cancelamento_snapshot(obj)['motivo_visual']

    def get_protocolo_cancelamento(self, obj):
        return _cancelamento_snapshot(obj)['protocolo_cancelamento']

    def get_empresa_id(self, obj):
        return obj.empresa_emitente_id

    def get_empresa_nome(self, obj):
        return obj.empresa_emitente.razao_social if obj.empresa_emitente_id else ''

    def get_papel_empresa(self, obj):
        return obj.papel_empresa_no_documento or ('emitente' if obj.empresa_emitente_id else '')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in (
            'valor_produtos',
            'valor_total_nf',
            'v_frete',
            'v_seg',
            'v_desc',
            'v_outro',
        ):
            if k in data and data[k] is not None:
                data[k] = float(data[k])
        data['dh_emissao'] = instance.dh_emissao.isoformat() if instance.dh_emissao else None
        data['importado_em'] = instance.importado_em.isoformat() if instance.importado_em else None
        data['data_cancelamento'] = instance.data_cancelamento.isoformat() if instance.data_cancelamento else None
        return data


class CTeEntradaSerializer(serializers.ModelSerializer):
    transportadora_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora',
    )
    tomador_id = serializers.PrimaryKeyRelatedField(queryset=Empresa.objects.all(), source='tomador')
    transportadora_nome = serializers.SerializerMethodField(read_only=True)
    tomador_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CTeEntrada
        fields = (
            'id',
            'numero',
            'transportadora_id',
            'transportadora_nome',
            'tomador_id',
            'tomador_nome',
            'valor_frete',
            'data',
            'nfe_ids',
        )

    def get_transportadora_nome(self, obj):
        return obj.transportadora.razao_social

    def get_tomador_nome(self, obj):
        return obj.tomador.razao_social

    def validate_nfe_ids(self, value):
        if not value:
            return value
        found = set(NFeEntrada.objects.filter(pk__in=value).values_list('pk', flat=True))
        missing = set(value) - found
        if missing:
            raise serializers.ValidationError(f'NF-e de entrada inexistentes: {sorted(missing)}')
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['transportadora_id'] = instance.transportadora_id
        data['tomador_id'] = instance.tomador_id
        data['data'] = instance.data.isoformat()
        data['valor_frete'] = float(instance.valor_frete)
        return data


def _cte_status_visual(obj: CTeHistoricoImportado) -> dict[str, Any]:
    if obj.cancelado:
        return {
            'status_visual': 'cancelado',
            'cstat_visual': obj.cstat or '101',
            'motivo_visual': obj.motivo_cancelamento or obj.xmotivo or 'CT-e cancelado',
        }
    if obj.cstat:
        return {
            'status_visual': obj.status_documento or ('autorizado' if obj.cstat == '100' else 'pendente'),
            'cstat_visual': obj.cstat,
            'motivo_visual': obj.xmotivo or '',
        }
    return {'status_visual': obj.status_documento or 'pendente', 'cstat_visual': '', 'motivo_visual': obj.xmotivo or ''}


class EventoCTeHistoricoImportadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoCTeHistoricoImportado
        fields = (
            'id',
            'chave_acesso',
            'tipo_evento',
            'protocolo_evento',
            'id_evento',
            'sequencial_evento',
            'data_evento',
            'evento_json',
            'nome_arquivo',
            'importado_em',
        )


class CTeHistoricoImportadoListSerializer(serializers.ModelSerializer):
    transportadora_nome = serializers.SerializerMethodField(read_only=True)
    empresa_tomadora_nome = serializers.SerializerMethodField(read_only=True)
    status_visual = serializers.SerializerMethodField(read_only=True)
    cstat_visual = serializers.SerializerMethodField(read_only=True)
    motivo_visual = serializers.SerializerMethodField(read_only=True)
    empresa_id = serializers.SerializerMethodField(read_only=True)
    empresa_nome = serializers.SerializerMethodField(read_only=True)
    papel_empresa = serializers.SerializerMethodField(read_only=True)
    fornecedor_remetente_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CTeHistoricoImportado
        fields = (
            'id',
            'chave_acesso',
            'numero',
            'serie',
            'dh_emissao',
            'valor_total_servico',
            'valor_receber',
            'icms_base',
            'icms_aliquota',
            'icms_valor',
            'modal',
            'tipo_servico',
            'municipio_inicio',
            'uf_inicio',
            'municipio_fim',
            'uf_fim',
            'cstat',
            'protocolo',
            'transportadora',
            'transportadora_nome',
            'empresa_tomadora',
            'empresa_tomadora_nome',
            'empresa_destinataria',
            'empresa_recebedora',
            'fornecedor_remetente',
            'fornecedor_remetente_nome',
            'empresa_id',
            'empresa_nome',
            'papel_empresa',
            'papel_empresa_no_documento',
            'cancelado',
            'status_documento',
            'data_cancelamento',
            'protocolo_cancelamento',
            'motivo_cancelamento',
            'status_visual',
            'cstat_visual',
            'motivo_visual',
            'nome_arquivo',
            'importado_em',
            'importado',
            'origem_externa',
            'historico',
        )

    def get_transportadora_nome(self, obj):
        return obj.transportadora.razao_social if obj.transportadora_id else (obj.emit_json or {}).get('xNome', '')

    def get_empresa_tomadora_nome(self, obj):
        return obj.empresa_tomadora.razao_social if obj.empresa_tomadora_id else ''

    def get_status_visual(self, obj):
        return _cte_status_visual(obj)['status_visual']

    def get_cstat_visual(self, obj):
        return _cte_status_visual(obj)['cstat_visual']

    def get_motivo_visual(self, obj):
        return _cte_status_visual(obj)['motivo_visual']

    def get_fornecedor_remetente_nome(self, obj):
        return obj.fornecedor_remetente.razao_social if obj.fornecedor_remetente_id else (obj.rem_json or {}).get('xNome', '')

    def get_empresa_id(self, obj):
        if obj.empresa_tomadora_id:
            return obj.empresa_tomadora_id
        if obj.empresa_destinataria_id:
            return obj.empresa_destinataria_id
        if obj.empresa_recebedora_id:
            return obj.empresa_recebedora_id
        return None

    def get_empresa_nome(self, obj):
        if obj.empresa_tomadora_id:
            return obj.empresa_tomadora.razao_social
        if obj.empresa_destinataria_id:
            return obj.empresa_destinataria.razao_social
        if obj.empresa_recebedora_id:
            return obj.empresa_recebedora.razao_social
        return ''

    def get_papel_empresa(self, obj):
        return obj.papel_empresa_no_documento or ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('valor_total_servico', 'valor_receber', 'icms_base', 'icms_aliquota', 'icms_valor'):
            if k in data and data[k] is not None:
                data[k] = float(getattr(instance, k))
        data['dh_emissao'] = instance.dh_emissao.isoformat() if instance.dh_emissao else None
        data['importado_em'] = instance.importado_em.isoformat() if instance.importado_em else None
        data['data_cancelamento'] = instance.data_cancelamento.isoformat() if instance.data_cancelamento else None
        return data


class CTeHistoricoImportadoSerializer(serializers.ModelSerializer):
    transportadora_nome = serializers.SerializerMethodField(read_only=True)
    empresa_tomadora_nome = serializers.SerializerMethodField(read_only=True)
    status_visual = serializers.SerializerMethodField(read_only=True)
    cstat_visual = serializers.SerializerMethodField(read_only=True)
    motivo_visual = serializers.SerializerMethodField(read_only=True)
    eventos = EventoCTeHistoricoImportadoSerializer(many=True, read_only=True)
    empresa_id = serializers.SerializerMethodField(read_only=True)
    empresa_nome = serializers.SerializerMethodField(read_only=True)
    papel_empresa = serializers.SerializerMethodField(read_only=True)
    fornecedor_remetente_nome = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CTeHistoricoImportado
        fields = (
            'id',
            'chave_acesso',
            'numero',
            'serie',
            'modelo',
            'dh_emissao',
            'tp_amb',
            'nat_op',
            'cfop',
            'versao_layout',
            'cstat',
            'xmotivo',
            'protocolo',
            'cancelado',
            'status_documento',
            'data_cancelamento',
            'protocolo_cancelamento',
            'motivo_cancelamento',
            'valor_total_servico',
            'valor_receber',
            'componentes_frete_json',
            'icms_base',
            'icms_aliquota',
            'icms_valor',
            'modal',
            'tipo_servico',
            'municipio_inicio',
            'uf_inicio',
            'municipio_fim',
            'uf_fim',
            'emit_json',
            'rem_json',
            'dest_json',
            'exped_json',
            'receb_json',
            'tomador_json',
            'totais_json',
            'imposto_json',
            'prot_json',
            'reforma_e_outros_json',
            'chaves_nfe_vinculadas',
            'transportadora',
            'transportadora_nome',
            'empresa_tomadora',
            'empresa_tomadora_nome',
            'empresa_destinataria',
            'empresa_recebedora',
            'fornecedor_remetente',
            'fornecedor_remetente_nome',
            'empresa_id',
            'empresa_nome',
            'papel_empresa',
            'papel_empresa_no_documento',
            'status_visual',
            'cstat_visual',
            'motivo_visual',
            'nome_arquivo',
            'importado_em',
            'importado',
            'origem_externa',
            'historico',
            'eventos',
        )

    def get_transportadora_nome(self, obj):
        return obj.transportadora.razao_social if obj.transportadora_id else (obj.emit_json or {}).get('xNome', '')

    def get_empresa_tomadora_nome(self, obj):
        return obj.empresa_tomadora.razao_social if obj.empresa_tomadora_id else ''

    def get_status_visual(self, obj):
        return _cte_status_visual(obj)['status_visual']

    def get_cstat_visual(self, obj):
        return _cte_status_visual(obj)['cstat_visual']

    def get_motivo_visual(self, obj):
        return _cte_status_visual(obj)['motivo_visual']

    def get_fornecedor_remetente_nome(self, obj):
        return obj.fornecedor_remetente.razao_social if obj.fornecedor_remetente_id else (obj.rem_json or {}).get('xNome', '')

    def get_empresa_id(self, obj):
        if obj.empresa_tomadora_id:
            return obj.empresa_tomadora_id
        if obj.empresa_destinataria_id:
            return obj.empresa_destinataria_id
        if obj.empresa_recebedora_id:
            return obj.empresa_recebedora_id
        return None

    def get_empresa_nome(self, obj):
        if obj.empresa_tomadora_id:
            return obj.empresa_tomadora.razao_social
        if obj.empresa_destinataria_id:
            return obj.empresa_destinataria.razao_social
        if obj.empresa_recebedora_id:
            return obj.empresa_recebedora.razao_social
        return ''

    def get_papel_empresa(self, obj):
        return obj.papel_empresa_no_documento or ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('valor_total_servico', 'valor_receber', 'icms_base', 'icms_aliquota', 'icms_valor'):
            if k in data and data[k] is not None:
                data[k] = float(getattr(instance, k))
        data['dh_emissao'] = instance.dh_emissao.isoformat() if instance.dh_emissao else None
        data['importado_em'] = instance.importado_em.isoformat() if instance.importado_em else None
        data['data_cancelamento'] = instance.data_cancelamento.isoformat() if instance.data_cancelamento else None
        return data


class AtendimentoEstoqueListSerializer(serializers.ModelSerializer):
    produto_id = serializers.IntegerField(source='produto.id', read_only=True)
    produto_codigo = serializers.CharField(source='produto.codigo_completo', read_only=True)
    produto_descricao = serializers.CharField(source='produto.descricao', read_only=True)
    quantidade_pendente = serializers.SerializerMethodField()
    nf_saida_id = serializers.IntegerField(source='nf_saida.id', read_only=True)
    numero_nf_saida = serializers.CharField(source='nf_saida.numero', read_only=True)
    cliente_id = serializers.SerializerMethodField()
    cliente_nome = serializers.SerializerMethodField()
    dias_em_aberto = serializers.SerializerMethodField()

    class Meta:
        model = AtendimentoEstoque
        fields = (
            'id',
            'status',
            'produto_id',
            'produto_codigo',
            'produto_descricao',
            'quantidade_comprometida',
            'quantidade_atendida',
            'quantidade_pendente',
            'unidade',
            'nf_saida_id',
            'numero_nf_saida',
            'cliente_id',
            'cliente_nome',
            'criado_em',
            'dias_em_aberto',
            'estoque_fisico_aplicado',
        )

    def get_quantidade_pendente(self, obj):
        return str(quantidade_pendente_atendimento(obj))

    def get_cliente_id(self, obj):
        return obj.nf_saida.cliente_id if obj.nf_saida_id else None

    def get_cliente_nome(self, obj):
        if obj.nf_saida_id and obj.nf_saida.cliente_id:
            return obj.nf_saida.cliente.razao_social
        return ''

    def get_dias_em_aberto(self, obj):
        return dias_em_aberto_atendimento(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['quantidade_comprometida'] = f'{instance.quantidade_comprometida:.3f}'
        data['quantidade_atendida'] = f'{instance.quantidade_atendida:.3f}'
        data['criado_em'] = instance.criado_em.isoformat() if instance.criado_em else None
        return data
