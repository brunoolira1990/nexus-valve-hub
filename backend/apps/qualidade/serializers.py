from rest_framework import serializers
from apps.produtos.snapshot import build_produto_snapshot
from apps.text_normalize import normalize_operational_fields, to_operational_upper

from .models import (
    Certificado,
    CertificadoFornecedorEntrada,
    CertificadoQualidade,
    ComponenteCertificadoFornecedorEntrada,
    ItemCertificadoFornecedorEntrada,
    ItemCertificadoQualidade,
    ItemCertificadoQualidadeComponente,
    _normalize_numero_cq,
    _split_numero_serie,
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
            'componentes',
        )

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
            'itens',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def get_numero_formatado(self, obj: CertificadoQualidade) -> str:
        return obj.numero_formatado

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
                'status',
                'tipo_certificado',
            },
        )
        if 'numero' in attrs:
            attrs['numero'] = to_operational_upper(attrs.get('numero')) or ''
        numero_in = attrs.get('numero') if 'numero' in attrs else (self.instance.numero if self.instance else '')
        serie_in = attrs.get('serie') if 'serie' in attrs else (self.instance.serie if self.instance else '')
        numero_sem_serie, serie_resolvida = _split_numero_serie(numero_in, serie_in)
        numero_normalizado = _normalize_numero_cq(numero_sem_serie)
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
            if not nf_ok:
                raise serializers.ValidationError({'nota_fiscal_numero': 'Informe a NF para emitir.'})
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
        return attrs

    def _upsert_itens(self, instance: CertificadoQualidade, itens_data: list[dict]):
        instance.itens.all().delete()
        for i, item in enumerate(itens_data, start=1):
            comps = item.pop('componentes', []) or []
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
        obj = CertificadoQualidade.objects.create(**validated_data)
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


class ItemCertificadoFornecedorEntradaSerializer(serializers.ModelSerializer):
    componentes = ComponenteCertificadoFornecedorEntradaSerializer(many=True, required=False)

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
            'componentes',
        )

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
        return attrs


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

    def validate(self, attrs):
        normalize_operational_fields(
            attrs,
            {
                'numero_certificado_fornecedor',
                'fornecedor_nome_snapshot',
                'fornecedor_cnpj_snapshot',
                'numero_nf_entrada',
                'serie_nf_entrada',
                'status',
            },
        )
        status_cert = attrs.get('status') or (
            self.instance.status if self.instance else CertificadoFornecedorEntrada.Status.RASCUNHO
        )
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
        return attrs

    def _upsert_itens(self, instance: CertificadoFornecedorEntrada, itens_data: list[dict]):
        instance.itens.all().delete()
        for i, item in enumerate(itens_data, start=1):
            comps = item.pop('componentes', []) or []
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
