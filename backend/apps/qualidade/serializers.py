import re
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.fields import empty

from apps.fiscal.conferencia_pedido import item_pedido_resumo_dict
from apps.fiscal.models import ItemNFeEntradaConferencia
from apps.produtos.snapshot import build_produto_snapshot
from apps.text_normalize import normalize_operational_fields, to_operational_upper

from .models import (
    Certificado,
    CertificadoFornecedorEntrada,
    CertificadoQualidade,
    ComponenteCertificadoFornecedorEntrada,
    ItemCertificadoFornecedorCorrida,
    ItemCertificadoFornecedorEntrada,
    ItemCertificadoQualidade,
    ItemCertificadoQualidadeComponente,
    _normalize_numero_cq,
    _split_numero_serie,
    normalizar_numero_cq_armazenamento,
)
from .rastreabilidade_cq import (
    avaliar_rastreabilidade_item_certificado_qualidade,
    montar_resumo_rastreabilidade_certificado,
    validar_rastreabilidade_emissao_certificado_qualidade,
)
from .services.numeracao_certificado_qualidade import (
    gerar_numero_certificado_qualidade,
    numero_certificado_qualidade_vazio,
)


class CertificadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificado
        fields = ('id', 'nf_saida', 'arquivo', 'gerado_em')
        read_only_fields = ('arquivo', 'gerado_em')


class ItemCertificadoQualidadeComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCertificadoQualidadeComponente
        fields = (
            'id',
            'ordem',
            'nome_componente',
            'descricao_componente',
            'norma',
            'corrida',
            'revisao_corrida',
            'numero_certificado_fornecedor_componente_snapshot',
            'quantidade',
            'composicao_json',
            'ensaio_tracao_json',
            'ensaio_impacto_json',
            'observacoes',
            'ativo',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'nome_componente',
                'descricao_componente',
                'norma',
                'corrida',
                'revisao_corrida',
                'numero_certificado_fornecedor_componente_snapshot',
                'observacoes',
            },
        )
        return attrs


class ItemCertificadoQualidadeSerializer(serializers.ModelSerializer):
    componentes = ItemCertificadoQualidadeComponenteSerializer(many=True, required=False)
    rastreabilidade_status = serializers.SerializerMethodField()
    rastreabilidade_label = serializers.SerializerMethodField()
    rastreabilidade_mensagens = serializers.SerializerMethodField()
    rastreabilidade_avisos = serializers.SerializerMethodField()
    rastreabilidade_motivos = serializers.SerializerMethodField()
    tem_certificado_fornecedor = serializers.SerializerMethodField()
    certificado_fornecedor_status = serializers.SerializerMethodField()
    tem_conferencia_origem = serializers.SerializerMethodField()
    estoque_aplicado_origem = serializers.SerializerMethodField()
    tem_corrida_lote = serializers.SerializerMethodField()

    class Meta:
        model = ItemCertificadoQualidade
        fields = (
            'id',
            'ordem',
            'produto',
            'codigo_produto',
            'descricao_material',
            'quantidade',
            'unidade',
            'norma',
            'corrida',
            'lote',
            'tipo_dados_tecnicos',
            'ncm',
            'observacoes_item',
            'composicao_json',
            'ensaio_tracao_json',
            'ensaio_impacto_json',
            'certificado_fornecedor_origem_id',
            'item_certificado_fornecedor_origem_id',
            'fornecedor_nome_snapshot',
            'nf_entrada_snapshot',
            'codigo_item_fornecedor_snapshot',
            'descricao_item_fornecedor_snapshot',
            'numero_certificado_fornecedor_item_snapshot',
            'corrida_snapshot',
            'lote_snapshot',
            'produto_snapshot',
            'origem_rastreabilidade_tipo',
            'origem_status_tecnico',
            'origem_observacoes',
            'incluir_no_certificado',
            'motivo_nao_inclusao',
            'observacao_nao_inclusao',
            'rastreabilidade_status',
            'rastreabilidade_label',
            'rastreabilidade_mensagens',
            'rastreabilidade_avisos',
            'rastreabilidade_motivos',
            'tem_certificado_fornecedor',
            'certificado_fornecedor_status',
            'tem_conferencia_origem',
            'estoque_aplicado_origem',
            'tem_corrida_lote',
            'componentes',
        )
        read_only_fields = (
            'rastreabilidade_status',
            'rastreabilidade_label',
            'rastreabilidade_mensagens',
            'rastreabilidade_avisos',
            'rastreabilidade_motivos',
            'tem_certificado_fornecedor',
            'certificado_fornecedor_status',
            'tem_conferencia_origem',
            'estoque_aplicado_origem',
            'tem_corrida_lote',
        )

    def _avaliacao_rastreabilidade(self, obj: ItemCertificadoQualidade) -> dict:
        cache = self.context.setdefault('_rastreabilidade_item_cache', {})
        key = obj.pk if obj.pk else id(obj)
        if key not in cache:
            cache[key] = avaliar_rastreabilidade_item_certificado_qualidade(obj)
        return cache[key]

    def get_rastreabilidade_status(self, obj: ItemCertificadoQualidade) -> str:
        return self._avaliacao_rastreabilidade(obj)['status']

    def get_rastreabilidade_label(self, obj: ItemCertificadoQualidade) -> str:
        return self._avaliacao_rastreabilidade(obj)['label']

    def get_rastreabilidade_mensagens(self, obj: ItemCertificadoQualidade) -> list[str]:
        return self._avaliacao_rastreabilidade(obj)['mensagens']

    def get_rastreabilidade_avisos(self, obj: ItemCertificadoQualidade) -> list[str]:
        return self._avaliacao_rastreabilidade(obj).get('avisos', [])

    def get_rastreabilidade_motivos(self, obj: ItemCertificadoQualidade) -> list[str]:
        return self._avaliacao_rastreabilidade(obj)['motivos']

    def get_tem_certificado_fornecedor(self, obj: ItemCertificadoQualidade) -> bool:
        return self._avaliacao_rastreabilidade(obj)['tem_certificado_fornecedor']

    def get_certificado_fornecedor_status(self, obj: ItemCertificadoQualidade) -> str | None:
        return self._avaliacao_rastreabilidade(obj)['certificado_fornecedor_status']

    def get_tem_conferencia_origem(self, obj: ItemCertificadoQualidade) -> bool:
        return self._avaliacao_rastreabilidade(obj)['tem_conferencia_origem']

    def get_estoque_aplicado_origem(self, obj: ItemCertificadoQualidade) -> bool:
        return self._avaliacao_rastreabilidade(obj)['estoque_aplicado_origem']

    def get_tem_corrida_lote(self, obj: ItemCertificadoQualidade) -> bool:
        return self._avaliacao_rastreabilidade(obj)['tem_corrida_lote']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'codigo_produto',
                'descricao_material',
                'unidade',
                'norma',
                'corrida',
                'lote',
                'tipo_dados_tecnicos',
                'ncm',
                'observacoes_item',
                'fornecedor_nome_snapshot',
                'nf_entrada_snapshot',
                'codigo_item_fornecedor_snapshot',
                'descricao_item_fornecedor_snapshot',
                'numero_certificado_fornecedor_item_snapshot',
                'corrida_snapshot',
                'lote_snapshot',
                'origem_rastreabilidade_tipo',
                'origem_status_tecnico',
                'origem_observacoes',
                'motivo_nao_inclusao',
                'observacao_nao_inclusao',
            },
        )
        produto = attrs.get('produto', getattr(self.instance, 'produto', None))
        if 'produto_snapshot' in attrs:
            snap = attrs.get('produto_snapshot') or {}
        else:
            snap = (self.instance.produto_snapshot if self.instance else {}) or {}
        if produto and (not snap or snap == {}):
            attrs['produto_snapshot'] = build_produto_snapshot(produto)
        return attrs


class CertificadoQualidadeSerializer(serializers.ModelSerializer):
    itens = ItemCertificadoQualidadeSerializer(many=True)
    numero_formatado = serializers.SerializerMethodField(read_only=True)
    resumo_rastreabilidade = serializers.SerializerMethodField(read_only=True)
    rastreabilidade_resumo_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CertificadoQualidade
        fields = (
            'id',
            'numero',
            'serie',
            'numero_formatado',
            'cliente',
            'cliente_nome_snapshot',
            'cliente_cnpj_snapshot',
            'pedido_cliente',
            'nota_fiscal_numero',
            'nota_fiscal',
            'nota_fiscal_historica',
            'data_emissao',
            'observacoes',
            'texto_padrao',
            'status',
            'tipo_certificado',
            'criado_em',
            'atualizado_em',
            'resumo_rastreabilidade',
            'rastreabilidade_resumo_label',
            'itens',
        )
        read_only_fields = ('criado_em', 'atualizado_em', 'resumo_rastreabilidade', 'rastreabilidade_resumo_label')

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields['numero'].read_only = True
        return fields

    def get_numero_formatado(self, obj: CertificadoQualidade) -> str:
        return obj.numero_formatado

    def get_resumo_rastreabilidade(self, obj: CertificadoQualidade) -> dict:
        itens = list(obj.itens.prefetch_related('componentes').all())
        return montar_resumo_rastreabilidade_certificado(itens)

    def get_rastreabilidade_resumo_label(self, obj: CertificadoQualidade) -> str:
        resumo = self.get_resumo_rastreabilidade(obj)
        if resumo['pode_emitir']:
            return 'Rastreabilidade completa'
        if resumo['pendentes'] > 0:
            return 'Rastreabilidade pendente'
        if resumo['parciais'] > 0:
            return 'Rastreabilidade parcial'
        return 'Rastreabilidade pendente'

    def _resolve_data_emissao_from_nf(self, attrs) -> object | None:
        nf = attrs.get('nota_fiscal') if 'nota_fiscal' in attrs else (self.instance.nota_fiscal if self.instance else None)
        nf_hist = (
            attrs.get('nota_fiscal_historica')
            if 'nota_fiscal_historica' in attrs
            else (self.instance.nota_fiscal_historica if self.instance else None)
        )
        if nf and getattr(nf, 'data', None):
            return nf.data
        if nf_hist and getattr(nf_hist, 'dh_emissao', None):
            dh = nf_hist.dh_emissao
            return dh.date() if hasattr(dh, 'date') else dh
        return None

    def validate(self, attrs):
        normalize_operational_fields(
            attrs,
            {
                'serie',
                'cliente_nome_snapshot',
                'cliente_cnpj_snapshot',
                'pedido_cliente',
                'nota_fiscal_numero',
                'tipo_certificado',
            },
        )
        if 'numero' in attrs:
            attrs['numero'] = to_operational_upper(attrs.get('numero')) or ''
        if self.instance:
            if numero_certificado_qualidade_vazio(self.instance.numero):
                attrs['numero'] = gerar_numero_certificado_qualidade()
            else:
                attrs['numero'] = self.instance.numero
        elif numero_certificado_qualidade_vazio(attrs.get('numero', '')):
            attrs['numero'] = gerar_numero_certificado_qualidade()
        numero_in = attrs.get('numero') if 'numero' in attrs else (self.instance.numero if self.instance else '')
        serie_in = attrs.get('serie') if 'serie' in attrs else (self.instance.serie if self.instance else '')
        numero_sem_serie, serie_resolvida = _split_numero_serie(numero_in, serie_in)
        numero_normalizado = normalizar_numero_cq_armazenamento(numero_sem_serie)
        attrs['numero'] = numero_normalizado
        attrs['serie'] = serie_resolvida
        if numero_normalizado:
            conflito = CertificadoQualidade.objects.filter(numero=numero_normalizado, serie=serie_resolvida)
            if self.instance:
                conflito = conflito.exclude(pk=self.instance.pk)
            if conflito.exists():
                raise serializers.ValidationError({'numero': 'Já existe certificado com este número/série normalizados.'})

        data_nf = self._resolve_data_emissao_from_nf(attrs)
        if data_nf is not None:
            attrs['data_emissao'] = data_nf
        itens = attrs.get('itens')
        status_cert = attrs.get('status') or (self.instance.status if self.instance else CertificadoQualidade.Status.RASCUNHO)
        cliente_ok = attrs.get('cliente') or attrs.get('cliente_nome_snapshot') or (self.instance and (self.instance.cliente_id or self.instance.cliente_nome_snapshot))
        nf_ok = (
            attrs.get('nota_fiscal')
            or attrs.get('nota_fiscal_historica')
            or attrs.get('nota_fiscal_numero')
            or (self.instance and (self.instance.nota_fiscal_id or self.instance.nota_fiscal_historica_id or self.instance.nota_fiscal_numero))
        )
        if 'nota_fiscal' in attrs and attrs.get('nota_fiscal') is not None:
            from apps.qualidade.nfe_elegivel_cq import MSG_NFE_INELEGIVEL_CQ, nfe_elegivel_para_certificado_qualidade

            nf_sel = attrs['nota_fiscal']
            nf_id = getattr(nf_sel, 'pk', nf_sel)
            vinculo_legado_inalterado = (
                self.instance is not None and self.instance.nota_fiscal_id == nf_id
            )
            if not vinculo_legado_inalterado and not nfe_elegivel_para_certificado_qualidade(nf_sel):
                raise serializers.ValidationError({'nota_fiscal': MSG_NFE_INELEGIVEL_CQ})
        if status_cert == CertificadoQualidade.Status.RASCUNHO:
            if not (cliente_ok or nf_ok):
                raise serializers.ValidationError({'detail': 'Para salvar rascunho, informe cliente ou selecione a NF.'})
        if status_cert == CertificadoQualidade.Status.EMITIDO:
            numero_ok = attrs.get('numero') if 'numero' in attrs else (self.instance.numero if self.instance else '')
            data_ok = attrs.get('data_emissao') if 'data_emissao' in attrs else (self.instance.data_emissao if self.instance else None)
            if not (numero_ok or '').strip():
                raise serializers.ValidationError({'numero': 'Informe o número do certificado para emitir.'})
            if not str(numero_ok).startswith('CQ'):
                raise serializers.ValidationError({'numero': 'O número do certificado emitido deve iniciar com CQ.'})
            if not cliente_ok:
                raise serializers.ValidationError({'cliente_nome_snapshot': 'Informe o cliente para emitir.'})
            if not data_ok:
                raise serializers.ValidationError({'data_emissao': 'Informe a data de emissão.'})
            base = itens if itens is not None else list(
                self.instance.itens.all().values('tipo_dados_tecnicos', 'incluir_no_certificado')
            )
            if not base:
                raise serializers.ValidationError({'itens': 'Informe pelo menos um item antes de emitir.'})
            incluidos = [
                it for it in base
                if bool((it.get('incluir_no_certificado', True) if isinstance(it, dict) else True))
            ]
            if not incluidos:
                raise serializers.ValidationError({'itens': 'O certificado precisa ter pelo menos um item incluído.'})
            for idx, it in enumerate(base, start=1):
                if isinstance(it, dict) and not bool(it.get('incluir_no_certificado', True)):
                    continue
                tipo = it.get('tipo_dados_tecnicos') if isinstance(it, dict) else it['tipo_dados_tecnicos']
                if tipo == ItemCertificadoQualidade.TipoDadosTecnicos.VALVULA_COMPONENTES:
                    comps = it.get('componentes') if isinstance(it, dict) else None
                    if comps is not None and len(comps) == 0:
                        raise serializers.ValidationError({'itens': f'Item {idx} está marcado como válvula, mas sem componentes.'})
            itens_para_rastreio = base
            if itens is None and self.instance:
                itens_para_rastreio = list(
                    self.instance.itens.prefetch_related('componentes').all(),
                )
            erros_rastreio = validar_rastreabilidade_emissao_certificado_qualidade(itens_para_rastreio)
            if erros_rastreio:
                raise serializers.ValidationError(
                    {
                        'detail': (
                            'A emissão definitiva exige produto/descrição e dados técnicos '
                            'mínimos nos itens incluídos. Estoque e rastreabilidade física são opcionais.'
                        ),
                        'rastreabilidade': erros_rastreio,
                    },
                )
        return attrs

    def _upsert_itens(self, instance: CertificadoQualidade, itens_data: list[dict]):
        instance.itens.all().delete()
        for i, item in enumerate(itens_data, start=1):
            comps = item.pop('componentes', []) or []
            tem_cf = bool(
                item.get('certificado_fornecedor_origem_id')
                or item.get('item_certificado_fornecedor_origem_id')
            )
            if not tem_cf and not (item.get('origem_rastreabilidade_tipo') or '').strip():
                item['origem_rastreabilidade_tipo'] = 'manual'
            obj = ItemCertificadoQualidade.objects.create(
                certificado=instance,
                ordem=item.get('ordem') or i,
                **{k: v for k, v in item.items() if k != 'ordem'},
            )
            for j, comp in enumerate(comps, start=1):
                ItemCertificadoQualidadeComponente.objects.create(
                    item_certificado=obj,
                    ordem=comp.get('ordem') or j,
                    **{k: v for k, v in comp.items() if k != 'ordem'},
                )

    def create(self, validated_data):
        itens = validated_data.pop('itens', [])
        if numero_certificado_qualidade_vazio(validated_data.get('numero')):
            validated_data['numero'] = gerar_numero_certificado_qualidade()
        obj = CertificadoQualidade.objects.create(**validated_data)
        self._upsert_itens(obj, itens)
        return obj

    def update(self, instance, validated_data):
        if (instance.numero or '').strip():
            validated_data.pop('numero', None)
        itens = validated_data.pop('itens', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if itens is not None:
            self._upsert_itens(instance, itens)
        return instance


class ComponenteCertificadoFornecedorEntradaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponenteCertificadoFornecedorEntrada
        fields = (
            'id',
            'ordem',
            'nome_componente',
            'descricao_componente',
            'norma',
            'corrida',
            'lote',
            'revisao_corrida',
            'numero_certificado_fornecedor_componente',
            'quantidade',
            'composicao_json',
            'ensaio_tracao_json',
            'ensaio_impacto_json',
            'observacoes',
            'ativo',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'nome_componente',
                'descricao_componente',
                'norma',
                'corrida',
                'lote',
                'revisao_corrida',
                'numero_certificado_fornecedor_componente',
                'observacoes',
            },
        )
        return attrs


class ItemCertificadoFornecedorCorridaSerializer(serializers.ModelSerializer):
    # `id` gravável apenas para identificar linhas históricas reais na validação
    # (`_linha_adicional_legada_sem_quantidade`); nunca é usado sem conferir o banco.
    id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = ItemCertificadoFornecedorCorrida
        fields = (
            'id',
            'ordem',
            'corrida',
            'lote',
            'quantidade',
            'criado_em',
        )
        read_only_fields = ('criado_em',)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'corrida',
                'lote',
            },
        )
        return attrs


def _origem_pedido_compra_de_item_cf(item_conf: ItemNFeEntradaConferencia | None) -> dict | None:
    if not item_conf or not item_conf.item_pedido_compra_id:
        return None
    item_pc = item_conf.item_pedido_compra
    if not item_pc:
        return None
    resumo = item_pedido_resumo_dict(item_conf) or {}
    prod = item_pc.produto
    return {
        'pedido_compra_id': item_pc.pedido_id,
        'pedido_compra_numero': resumo.get('pedido_numero') or (item_pc.pedido.numero if item_pc.pedido_id else ''),
        'item_pedido_compra_id': item_pc.id,
        'item_pedido_resumo': resumo,
        'produto_pedido_codigo': resumo.get('codigo') or (prod.codigo_completo if prod else ''),
        'produto_pedido_descricao': resumo.get('descricao') or (prod.descricao if prod else ''),
        'quantidade_pedido': resumo.get('quantidade', ''),
        'unidade_pedido': resumo.get('unidade', ''),
        'valor_unitario_pedido': resumo.get('valor_unitario', ''),
    }


def _origem_display_item_cf(item_conf: ItemNFeEntradaConferencia | None) -> str:
    if not item_conf:
        return ''
    nf = item_conf.conferencia.nf_entrada_historica
    n_item = item_conf.item_nfe_historico.n_item if item_conf.item_nfe_historico_id else ''
    numero = nf.numero if nf else ''
    serie = nf.serie if nf else ''
    return f'NF {numero}/{serie} · item {n_item} · Conferência'


def _apply_origem_vinculo_item_cf(attrs: dict, item_conf: ItemNFeEntradaConferencia | None, instance=None) -> None:
    if not item_conf:
        return
    if instance is None or instance.item_conferencia_id != item_conf.pk:
        attrs.setdefault('origem_vinculada_em', timezone.now())
    if item_conf.item_nfe_historico_id:
        attrs.setdefault('origem_nfe_item_numero', item_conf.item_nfe_historico.n_item)


MSG_CORRIDA_LOTE_DUPLICADA_ITEM_CF = 'Esta corrida/lote já está vinculada a este item do certificado.'
MSG_SOMA_CORRIDAS_EXCEDE_ITEM_CF = 'A soma das quantidades das corridas excede a quantidade do item.'
MSG_QUANTIDADE_CORRIDA_ADICIONAL_INVALIDA = 'Informe quantidade maior que zero para a corrida adicional.'
MSG_PRINCIPAL_SEM_QUANTIDADE_ITEM_CF = (
    'A distribuição deixa a corrida principal sem quantidade. '
    'Ajuste as quantidades ou represente a origem em outro item do certificado.'
)


def _chave_corrida_lote_normalizada(corrida: str | None, lote: str | None) -> str:
    """Chave de duplicidade: caixa alta e sem espaços (diferenças triviais não contam)."""
    c = re.sub(r'\s+', '', (corrida or '').upper())
    l = re.sub(r'\s+', '', (lote or '').upper())
    if not c and not l:
        return ''
    return f'{c}\x1f{l}'


def _linha_adicional_legada_sem_quantidade(
    row: dict,
    certificado: CertificadoFornecedorEntrada | None,
) -> bool:
    """Linha histórica real sem quantidade — validada contra o estado PERSISTIDO, antes do
    delete/recreate do `_upsert_itens`. Não confia no `id` enviado pelo cliente: exige que o
    registro exista no CF em edição, já esteja sem quantidade e tenha a mesma corrida/lote.
    """
    row_id = row.get('id')
    if certificado is None or certificado.pk is None or not row_id:
        return False
    persistida = ItemCertificadoFornecedorCorrida.objects.filter(
        pk=row_id,
        item_certificado__certificado_fornecedor=certificado,
        quantidade__isnull=True,
    ).first()
    if persistida is None:
        return False
    return _chave_corrida_lote_normalizada(persistida.corrida, persistida.lote) == _chave_corrida_lote_normalizada(
        row.get('corrida'), row.get('lote'),
    )


def validar_corridas_adicionais_item_cf(
    *,
    quantidade_item,
    corrida_principal: str | None,
    lote_principal: str | None,
    corridas_adicionais: list[dict],
    certificado: CertificadoFornecedorEntrada | None = None,
) -> list[str]:
    """Valida corridas adicionais de um item do CF (mesmos dados técnicos do principal).

    Regras A1 (quantidade da principal é derivada: total − soma das adicionais):
    - quantidade obrigatória e > 0, exceto para linha histórica real já persistida sem
      quantidade neste certificado (compatibilidade, sem backfill);
    - a mesma combinação corrida+lote (normalizada) não pode repetir no item, incluindo a principal;
    - a soma das adicionais não pode exceder a quantidade do item;
    - com a corrida principal preenchida, a soma não pode igualar o total (principal ficaria sem quantidade).
    """
    erros: list[str] = []
    chaves_vistas: set[str] = set()
    chave_principal = _chave_corrida_lote_normalizada(corrida_principal, lote_principal)
    if chave_principal:
        chaves_vistas.add(chave_principal)

    soma_adicionais = Decimal('0')
    duplicada_reportada = False
    quantidade_invalida_reportada = False
    for row in corridas_adicionais:
        if not isinstance(row, dict):
            continue
        corrida = (row.get('corrida') or '').strip()
        lote = (row.get('lote') or '').strip()
        quantidade = row.get('quantidade')
        chave = _chave_corrida_lote_normalizada(corrida, lote)
        if chave:
            if chave in chaves_vistas and not duplicada_reportada:
                erros.append(MSG_CORRIDA_LOTE_DUPLICADA_ITEM_CF)
                duplicada_reportada = True
            chaves_vistas.add(chave)
        if quantidade is None:
            if not _linha_adicional_legada_sem_quantidade(row, certificado) and not quantidade_invalida_reportada:
                erros.append(MSG_QUANTIDADE_CORRIDA_ADICIONAL_INVALIDA)
                quantidade_invalida_reportada = True
            continue
        quantidade_dec = Decimal(str(quantidade))
        if quantidade_dec <= 0:
            if not quantidade_invalida_reportada:
                erros.append(MSG_QUANTIDADE_CORRIDA_ADICIONAL_INVALIDA)
                quantidade_invalida_reportada = True
        else:
            soma_adicionais += quantidade_dec

    if quantidade_item is not None:
        quantidade_item_dec = Decimal(str(quantidade_item))
        if quantidade_item_dec > 0 and soma_adicionais > 0:
            if soma_adicionais > quantidade_item_dec:
                erros.append(MSG_SOMA_CORRIDAS_EXCEDE_ITEM_CF)
            elif soma_adicionais == quantidade_item_dec and chave_principal:
                erros.append(MSG_PRINCIPAL_SEM_QUANTIDADE_ITEM_CF)
    return erros


def sincronizar_corridas_adicionais_item_cf(
    item: ItemCertificadoFornecedorEntrada,
    corridas_data: list[dict] | None,
) -> None:
    """Upsert de corridas adicionais por ordem; remove linhas ausentes do payload."""
    if corridas_data is None:
        return

    if not corridas_data:
        item.corridas_adicionais.all().delete()
        return

    ordens_payload: set[int] = set()
    for idx, row in enumerate(corridas_data, start=1):
        if not isinstance(row, dict):
            continue
        ordem = int(row.get('ordem') or idx)
        ordens_payload.add(ordem)
        defaults = {
            'corrida': (row.get('corrida') or '').strip(),
            'lote': (row.get('lote') or '').strip(),
            'quantidade': row.get('quantidade'),
        }
        row_id = row.get('id')
        if row_id:
            updated = ItemCertificadoFornecedorCorrida.objects.filter(
                pk=row_id,
                item_certificado=item,
            ).update(ordem=ordem, **defaults)
            if updated:
                continue
        ItemCertificadoFornecedorCorrida.objects.update_or_create(
            item_certificado=item,
            ordem=ordem,
            defaults=defaults,
        )

    item.corridas_adicionais.exclude(ordem__in=ordens_payload).delete()


def _validate_item_conferencia_para_certificado(
    item_conf: ItemNFeEntradaConferencia,
    nf_entrada_historica_id: int | None,
    certificado_fornecedor_id: int | None,
    *,
    exclude_item_ids: set[int] | None = None,
) -> None:
    if not nf_entrada_historica_id:
        raise serializers.ValidationError(
            {'item_conferencia_id': 'Vincule a conferência apenas em certificados com NF-e de entrada histórica.'},
        )
    conf_nf_id = (
        ItemNFeEntradaConferencia.objects.filter(pk=item_conf.pk)
        .values_list('conferencia__nf_entrada_historica_id', flat=True)
        .first()
    )
    if conf_nf_id != nf_entrada_historica_id:
        raise serializers.ValidationError(
            {'item_conferencia_id': 'O item da conferência não pertence à NF-e de entrada deste certificado.'},
        )
    qs = ItemCertificadoFornecedorEntrada.objects.filter(item_conferencia=item_conf, ativo=True)
    if certificado_fornecedor_id:
        qs = qs.exclude(certificado_fornecedor_id=certificado_fornecedor_id)
    if exclude_item_ids:
        qs = qs.exclude(pk__in=exclude_item_ids)
    if qs.exists():
        raise serializers.ValidationError(
            {'item_conferencia_id': 'Esta linha da conferência já está vinculada a outro item ativo do certificado fornecedor.'},
        )


class ItemCertificadoFornecedorEntradaSerializer(serializers.ModelSerializer):
    componentes = ComponenteCertificadoFornecedorEntradaSerializer(many=True, required=False)
    corridas_adicionais = ItemCertificadoFornecedorCorridaSerializer(many=True, required=False)
    item_conferencia_id = serializers.PrimaryKeyRelatedField(
        source='item_conferencia',
        queryset=ItemNFeEntradaConferencia.objects.select_related(
            'conferencia__nf_entrada_historica',
            'item_nfe_historico',
            'item_pedido_compra__pedido',
            'item_pedido_compra__produto',
            'produto',
        ),
        required=False,
        allow_null=True,
    )
    origem_nfe_numero = serializers.SerializerMethodField()
    origem_nfe_serie = serializers.SerializerMethodField()
    origem_nfe_item_numero = serializers.IntegerField(read_only=True)
    origem_display = serializers.SerializerMethodField()
    origem_conferencia_status = serializers.SerializerMethodField()
    origem_produto_vinculado = serializers.SerializerMethodField()
    pedido_compra_id = serializers.SerializerMethodField()
    pedido_compra_numero = serializers.SerializerMethodField()
    item_pedido_compra_id = serializers.SerializerMethodField()
    item_pedido_resumo = serializers.SerializerMethodField()
    produto_pedido_codigo = serializers.SerializerMethodField()
    produto_pedido_descricao = serializers.SerializerMethodField()
    quantidade_pedido = serializers.SerializerMethodField()
    unidade_pedido = serializers.SerializerMethodField()
    valor_unitario_pedido = serializers.SerializerMethodField()
    origem_rastreabilidade_completa = serializers.SerializerMethodField()

    class Meta:
        model = ItemCertificadoFornecedorEntrada
        fields = (
            'id',
            'ordem',
            'produto',
            'codigo_produto',
            'descricao_material',
            'quantidade',
            'unidade',
            'ncm',
            'norma',
            'corrida',
            'lote',
            'numero_certificado_fornecedor_item',
            'data_certificado_fornecedor_item',
            'pagina_certificado_fornecedor',
            'observacao_origem_certificado',
            'tipo_dados_tecnicos',
            'composicao_json',
            'ensaio_tracao_json',
            'ensaio_impacto_json',
            'observacoes_item',
            'ativo',
            'item_conferencia_id',
            'origem_nfe_item_numero',
            'origem_vinculada_em',
            'origem_nfe_numero',
            'origem_nfe_serie',
            'origem_display',
            'origem_conferencia_status',
            'origem_produto_vinculado',
            'pedido_compra_id',
            'pedido_compra_numero',
            'item_pedido_compra_id',
            'item_pedido_resumo',
            'produto_pedido_codigo',
            'produto_pedido_descricao',
            'quantidade_pedido',
            'unidade_pedido',
            'valor_unitario_pedido',
            'origem_rastreabilidade_completa',
            'componentes',
            'corridas_adicionais',
        )
        read_only_fields = (
            'origem_nfe_numero',
            'origem_nfe_serie',
            'origem_nfe_item_numero',
            'origem_display',
            'origem_conferencia_status',
            'origem_produto_vinculado',
            'pedido_compra_id',
            'pedido_compra_numero',
            'item_pedido_compra_id',
            'item_pedido_resumo',
            'produto_pedido_codigo',
            'produto_pedido_descricao',
            'quantidade_pedido',
            'unidade_pedido',
            'valor_unitario_pedido',
            'origem_rastreabilidade_completa',
        )

    def get_origem_nfe_numero(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        if not obj.item_conferencia_id:
            return None
        nf = obj.item_conferencia.conferencia.nf_entrada_historica
        return nf.numero if nf else None

    def get_origem_nfe_serie(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        if not obj.item_conferencia_id:
            return None
        nf = obj.item_conferencia.conferencia.nf_entrada_historica
        return nf.serie if nf else None

    def get_origem_display(self, obj: ItemCertificadoFornecedorEntrada) -> str:
        if not obj.item_conferencia_id:
            return ''
        return _origem_display_item_cf(obj.item_conferencia)

    def get_origem_conferencia_status(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        if not obj.item_conferencia_id:
            return None
        return obj.item_conferencia.status

    def get_origem_produto_vinculado(self, obj: ItemCertificadoFornecedorEntrada) -> bool:
        if not obj.item_conferencia_id:
            return False
        return bool(obj.item_conferencia.produto_id)

    def get_pedido_compra_id(self, obj: ItemCertificadoFornecedorEntrada) -> int | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['pedido_compra_id'] if ctx else None

    def get_pedido_compra_numero(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['pedido_compra_numero'] if ctx else None

    def get_item_pedido_compra_id(self, obj: ItemCertificadoFornecedorEntrada) -> int | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['item_pedido_compra_id'] if ctx else None

    def get_item_pedido_resumo(self, obj: ItemCertificadoFornecedorEntrada) -> dict | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['item_pedido_resumo'] if ctx else None

    def get_produto_pedido_codigo(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['produto_pedido_codigo'] if ctx else None

    def get_produto_pedido_descricao(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['produto_pedido_descricao'] if ctx else None

    def get_quantidade_pedido(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['quantidade_pedido'] if ctx else None

    def get_unidade_pedido(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['unidade_pedido'] if ctx else None

    def get_valor_unitario_pedido(self, obj: ItemCertificadoFornecedorEntrada) -> str | None:
        ctx = _origem_pedido_compra_de_item_cf(
            obj.item_conferencia if obj.item_conferencia_id else None,
        )
        return ctx['valor_unitario_pedido'] if ctx else None

    def get_origem_rastreabilidade_completa(self, obj: ItemCertificadoFornecedorEntrada) -> bool:
        if not obj.item_conferencia_id:
            return False
        return bool(obj.item_conferencia.item_pedido_compra_id)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'codigo_produto',
                'descricao_material',
                'unidade',
                'ncm',
                'norma',
                'corrida',
                'lote',
                'numero_certificado_fornecedor_item',
                'pagina_certificado_fornecedor',
                'observacao_origem_certificado',
                'tipo_dados_tecnicos',
                'observacoes_item',
            },
        )
        corridas_adicionais = attrs.get('corridas_adicionais')
        if corridas_adicionais:
            erros_corridas = validar_corridas_adicionais_item_cf(
                quantidade_item=attrs.get(
                    'quantidade',
                    self.instance.quantidade if self.instance else None,
                ),
                corrida_principal=attrs.get('corrida', self.instance.corrida if self.instance else ''),
                lote_principal=attrs.get('lote', self.instance.lote if self.instance else ''),
                corridas_adicionais=corridas_adicionais,
                certificado=self.context.get('certificado_fornecedor'),
            )
            if erros_corridas:
                raise serializers.ValidationError({'corridas_adicionais': erros_corridas})
        if 'item_conferencia' in attrs:
            item_conf = attrs.get('item_conferencia')
            cert = self.context.get('certificado_fornecedor')
            nf_hist_id = self.context.get('nf_entrada_historica_id')
            if cert is not None and nf_hist_id is None:
                nf_hist_id = cert.nf_entrada_historica_id
            if item_conf:
                _validate_item_conferencia_para_certificado(
                    item_conf,
                    nf_hist_id,
                    cert.pk if cert else None,
                )
                _apply_origem_vinculo_item_cf(attrs, item_conf, self.instance)
            elif self.instance and self.instance.item_conferencia_id:
                attrs.setdefault('origem_vinculada_em', None)
                attrs.setdefault('origem_nfe_item_numero', None)
        return attrs


def _normalize_cf_status_value(value: str | None) -> str:
    if value is None or value == '':
        return ''
    return str(value).strip().lower()


class CertificadoFornecedorEntradaSerializer(serializers.ModelSerializer):
    itens = ItemCertificadoFornecedorEntradaSerializer(many=True, required=False)
    quantidade_itens = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CertificadoFornecedorEntrada
        fields = (
            'id',
            'numero_certificado_fornecedor',
            'fornecedor',
            'fornecedor_nome_snapshot',
            'fornecedor_cnpj_snapshot',
            'nf_entrada_historica',
            'nf_entrada_operacional',
            'numero_nf_entrada',
            'serie_nf_entrada',
            'data_nf_entrada',
            'empresa_destinataria',
            'status',
            'observacoes',
            'arquivo_original',
            'criado_em',
            'atualizado_em',
            'quantidade_itens',
            'itens',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def get_quantidade_itens(self, obj: CertificadoFornecedorEntrada) -> int:
        return obj.itens.count()

    def validate_status(self, value):
        if value is None or value == '':
            return value
        canonical = _normalize_cf_status_value(value)
        allowed = {choice.value for choice in CertificadoFornecedorEntrada.Status}
        if canonical not in allowed:
            raise serializers.ValidationError('Status inválido.')
        return canonical

    def validate(self, attrs):
        if 'status' in attrs and attrs['status'] is not None:
            attrs['status'] = self.validate_status(attrs['status'])
        normalize_operational_fields(
            attrs,
            {
                'numero_certificado_fornecedor',
                'fornecedor_nome_snapshot',
                'fornecedor_cnpj_snapshot',
                'numero_nf_entrada',
                'serie_nf_entrada',
            },
        )
        status_cert = _normalize_cf_status_value(
            attrs.get('status')
            or (self.instance.status if self.instance else CertificadoFornecedorEntrada.Status.RASCUNHO)
        )
        if 'status' in attrs:
            attrs['status'] = status_cert
        itens = attrs.get('itens')
        fornecedor_nome = attrs.get('fornecedor_nome_snapshot')
        if status_cert == CertificadoFornecedorEntrada.Status.REGISTRADO:
            fornecedor_ok = attrs.get('fornecedor') or fornecedor_nome or (
                self.instance and (self.instance.fornecedor_id or self.instance.fornecedor_nome_snapshot)
            )
            nf_ok = (
                attrs.get('nf_entrada_historica')
                or attrs.get('nf_entrada_operacional')
                or attrs.get('numero_nf_entrada')
                or (self.instance and (self.instance.nf_entrada_historica_id or self.instance.nf_entrada_operacional_id or self.instance.numero_nf_entrada))
            )
            if not fornecedor_ok:
                raise serializers.ValidationError({'fornecedor_nome_snapshot': 'Informe o fornecedor para registrar o certificado.'})
            if not nf_ok:
                raise serializers.ValidationError({'numero_nf_entrada': 'Informe a NF-e de entrada para registrar o certificado.'})
            numero_cabecalho = (
                (attrs.get('numero_certificado_fornecedor') if 'numero_certificado_fornecedor' in attrs else None)
                or (self.instance.numero_certificado_fornecedor if self.instance else '')
                or ''
            ).strip()
            if itens is not None:
                base_itens = itens
            elif self.instance:
                base_itens = []
                for db_item in self.instance.itens.prefetch_related('componentes').all():
                    base_itens.append(
                        {
                            'codigo_produto': db_item.codigo_produto,
                            'descricao_material': db_item.descricao_material,
                            'corrida': db_item.corrida,
                            'lote': db_item.lote,
                            'norma': db_item.norma,
                            'tipo_dados_tecnicos': db_item.tipo_dados_tecnicos,
                            'numero_certificado_fornecedor_item': db_item.numero_certificado_fornecedor_item,
                            'composicao_json': db_item.composicao_json,
                            'ensaio_tracao_json': db_item.ensaio_tracao_json,
                            'componentes': [
                                {
                                    'nome_componente': c.nome_componente,
                                    'corrida': c.corrida,
                                    'lote': c.lote,
                                    'norma': c.norma,
                                    'composicao_json': c.composicao_json,
                                    'ensaio_tracao_json': c.ensaio_tracao_json,
                                }
                                for c in db_item.componentes.all()
                            ],
                        }
                    )
            else:
                base_itens = []
            if not base_itens:
                raise serializers.ValidationError({'itens': 'Informe pelo menos um item para registrar o certificado.'})
            erros_itens: list[dict] = []
            for idx, item in enumerate(base_itens, start=1):
                codigo = (item.get('codigo_produto') or '').strip() if isinstance(item, dict) else ''
                descricao = (item.get('descricao_material') or '').strip() if isinstance(item, dict) else ''
                numero_item = (
                    (item.get('numero_certificado_fornecedor_item') or '').strip()
                    if isinstance(item, dict)
                    else ''
                )
                tipo = item.get('tipo_dados_tecnicos') if isinstance(item, dict) else ''
                item_errors: dict = {}
                if not codigo and not descricao:
                    item_errors['codigo_produto'] = ['Informe código ou descrição do item.']
                if not (numero_item or numero_cabecalho):
                    item_errors['numero_certificado_fornecedor_item'] = [
                        'Informe o número do certificado fornecedor do item ou cabeçalho.'
                    ]

                if tipo == ItemCertificadoFornecedorEntrada.TipoDadosTecnicos.VALVULA_COMPONENTES:
                    comps = item.get('componentes') if isinstance(item, dict) else None
                    if not comps:
                        item_errors['componentes'] = ['Informe ao menos um componente para válvula por componentes.']
                    else:
                        comp_errors: list[dict] = []
                        for comp in comps:
                            comp_error: dict = {}
                            corrida_comp = (comp.get('corrida') or '').strip() if isinstance(comp, dict) else ''
                            lote_comp = (comp.get('lote') or '').strip() if isinstance(comp, dict) else ''
                            norma_comp = (comp.get('norma') or '').strip() if isinstance(comp, dict) else ''
                            composicao_comp = comp.get('composicao_json') if isinstance(comp, dict) else {}
                            tracao_comp = comp.get('ensaio_tracao_json') if isinstance(comp, dict) else {}
                            has_comp = any(str(v or '').strip() for v in (composicao_comp or {}).values()) if isinstance(composicao_comp, dict) else False
                            has_trac = any(str(v or '').strip() for v in (tracao_comp or {}).values()) if isinstance(tracao_comp, dict) else False
                            if not (corrida_comp or lote_comp):
                                comp_error['corrida'] = ['Informe a corrida/lote.']
                            if not norma_comp:
                                comp_error['norma'] = ['Informe a norma.']
                            if not has_comp:
                                comp_error['composicao_json'] = ['Informe composição química.']
                            if not has_trac:
                                comp_error['ensaio_tracao_json'] = ['Informe propriedades mecânicas.']
                            comp_errors.append(comp_error)
                        if any(bool(e) for e in comp_errors):
                            item_errors['componentes'] = comp_errors
                else:
                    corrida = (item.get('corrida') or '').strip() if isinstance(item, dict) else ''
                    if not corrida:
                        item_errors['corrida'] = ['Informe a corrida/lote.']
                erros_itens.append(item_errors)
            if any(bool(e) for e in erros_itens):
                raise serializers.ValidationError({'itens': erros_itens})
        if itens is not None:
            vistos: set[int] = set()
            for idx, item in enumerate(itens):
                if not isinstance(item, dict):
                    continue
                item_conf = item.get('item_conferencia')
                if not item_conf:
                    continue
                ic_id = item_conf.pk
                if ic_id in vistos:
                    raise serializers.ValidationError(
                        {'itens': {idx: {'item_conferencia_id': ['Não repita a mesma linha da conferência em mais de um item.']}}},
                    )
                vistos.add(ic_id)
        return attrs

    def run_validation(self, data=empty):
        if data is not empty and isinstance(data, dict):
            nf_raw = data.get('nf_entrada_historica')
            nf_hist_id = nf_raw if isinstance(nf_raw, int) else (
                getattr(nf_raw, 'pk', None) if nf_raw is not None else None
            )
            if nf_hist_id is None and self.instance:
                nf_hist_id = self.instance.nf_entrada_historica_id
            self.fields['itens'].child.context.update(
                self._itens_child_context(self.instance, nf_hist_id),
            )
        return super().run_validation(data)

    def _upsert_itens(self, instance: CertificadoFornecedorEntrada, itens_data: list[dict]):
        instance.itens.all().delete()
        for i, item in enumerate(itens_data, start=1):
            comps = item.pop('componentes', []) or []
            corridas_extra = item.pop('corridas_adicionais', None)
            numero_item = (item.get('numero_certificado_fornecedor_item') or '').strip()
            numero_base = numero_item or (instance.numero_certificado_fornecedor or '').strip()
            obj = ItemCertificadoFornecedorEntrada.objects.create(
                certificado_fornecedor=instance,
                ordem=item.get('ordem') or i,
                **{k: v for k, v in item.items() if k != 'ordem'},
            )
            for j, comp in enumerate(comps, start=1):
                comp_data = {k: v for k, v in comp.items() if k != 'ordem'}
                if not (comp_data.get('numero_certificado_fornecedor_componente') or '').strip():
                    comp_data['numero_certificado_fornecedor_componente'] = numero_base
                ComponenteCertificadoFornecedorEntrada.objects.create(
                    item_certificado_fornecedor=obj,
                    ordem=comp.get('ordem') or j,
                    **comp_data,
                )
            sincronizar_corridas_adicionais_item_cf(obj, corridas_extra if corridas_extra is not None else [])

    def _itens_child_context(self, cert: CertificadoFornecedorEntrada | None, nf_hist_id: int | None) -> dict:
        return {
            'certificado_fornecedor': cert,
            'nf_entrada_historica_id': nf_hist_id,
        }

    def create(self, validated_data):
        itens = validated_data.pop('itens', [])
        obj = CertificadoFornecedorEntrada.objects.create(**validated_data)
        self._upsert_itens(obj, itens)
        return obj

    def update(self, instance, validated_data):
        itens = validated_data.pop('itens', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if itens is not None:
            self._upsert_itens(instance, itens)
        return instance
