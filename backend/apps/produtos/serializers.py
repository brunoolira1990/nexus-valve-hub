from decimal import Decimal

from django.db import IntegrityError
from rest_framework import serializers

from apps.produtos.codigo_produto import (
    codigo_interno_valido,
    montar_codigo_interno,
    montar_descricao_sugerida,
)
from apps.produtos.familia_regra import aplicar_flags_derivadas_no_dict, flags_por_tipo_regra
from apps.produtos.conversao_medidas import ConversaoErro, converter_quantidade_produto
from apps.produtos.polegadas import aliases_for_polegada, normalize_polegada_label, parse_polegada_to_decimal
from apps.text_normalize import normalize_operational_fields, to_operational_upper
from apps.produtos.models import (
    FamiliaProdutoPolegadaPermitida,
    FamiliaProdutoRoscaConexaoPermitida,
    FamiliaProdutoSchedulePermitido,
    FamiliaProduto,
    Ncm,
    Polegada,
    Produto,
    RoscaConexao,
    ScheduleEspessura,
)


class NcmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ncm
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'codigo', 'descricao'})
        return attrs


class PolegadaSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Polegada
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'codigo', 'codigo_oficial', 'descricao', 'origem', 'observacoes'})
        desc = attrs.get('descricao', getattr(self.instance, 'descricao', ''))
        normalized_desc = normalize_polegada_label(desc)
        if normalized_desc:
            attrs['descricao'] = normalized_desc
        valor_decimal = attrs.get('valor_decimal', getattr(self.instance, 'valor_decimal', None))
        if not valor_decimal:
            parsed = parse_polegada_to_decimal(attrs.get('descricao', ''))
            if parsed is not None:
                attrs['valor_decimal'] = parsed
                valor_decimal = parsed
        if valor_decimal and not attrs.get('valor_mm'):
            attrs['valor_mm'] = (valor_decimal * Decimal('25.4')).quantize(Decimal('0.001'))
        if valor_decimal and attrs.get('valor_mm') and attrs['valor_mm'] > Decimal('2540'):
            raise serializers.ValidationError({'valor_mm': 'Medida acima do limite operacional de 100".'})
        if not attrs.get('aliases'):
            mm = attrs.get('valor_mm') or getattr(self.instance, 'valor_mm', Decimal('0'))
            attrs['aliases'] = aliases_for_polegada(attrs.get('descricao', ''), valor_decimal or Decimal('0'), mm)
        if not attrs.get('codigo_oficial'):
            attrs['codigo_oficial'] = attrs.get('codigo') or getattr(self.instance, 'codigo', '')
        if not attrs.get('codigo'):
            attrs['codigo'] = attrs.get('codigo_oficial')
        return attrs

    def get_label(self, obj: Polegada):
        return f'{obj.codigo_oficial} — {obj.descricao} — {obj.valor_mm} mm'


class RoscaConexaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoscaConexao
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'codigo', 'descricao', 'observacao'})
        return attrs


class ScheduleEspessuraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleEspessura
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'codigo_schedule', 'descricao'})
        return attrs


class FamiliaProdutoSerializer(serializers.ModelSerializer):
    ncm_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Ncm.objects.all(),
        source='ncm_padrao',
        allow_null=True,
        required=False,
    )
    ncm_padrao_info = serializers.SerializerMethodField(read_only=True)
    polegadas_permitidas = serializers.SerializerMethodField(read_only=True)
    roscas_permitidas = serializers.SerializerMethodField(read_only=True)
    schedules_permitidos = serializers.SerializerMethodField(read_only=True)
    rosca_padrao_id = serializers.SerializerMethodField(read_only=True)
    schedule_padrao_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FamiliaProduto
        fields = '__all__'

    def validate(self, attrs):
        inst = self.instance
        normalize_operational_fields(
            attrs,
            {
                'codigo_figura',
                'descricao_base',
                'ncm_padrao',
                'unidade_padrao',
                'material_base',
                'pressao_base',
                'norma_base',
                'conexao_base',
                'tipo_fisico',
                'tipo_controle_unidade',
                'unidade_estoque_padrao',
                'unidade_venda_padrao',
                'unidade_compra_padrao',
                'unidade_fiscal_padrao',
                'observacoes_conversao',
            },
        )
        tipo = attrs.get('tipo_regra_codigo')
        if tipo is None and inst is not None:
            tipo = inst.tipo_regra_codigo
        if tipo is None:
            tipo = FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA
            attrs['tipo_regra_codigo'] = tipo
        aplicar_flags_derivadas_no_dict(attrs, tipo)
        return attrs

    def get_ncm_padrao_info(self, obj: FamiliaProduto):
        if not obj.ncm_padrao_id:
            return None
        return {
            'id': obj.ncm_padrao_id,
            'codigo': obj.ncm_padrao.codigo,
            'descricao': obj.ncm_padrao.descricao,
        }

    def get_polegadas_permitidas(self, obj: FamiliaProduto):
        return [
            {
                'id': rel.polegada_id,
                'codigo': rel.polegada.codigo,
                'descricao': rel.polegada.descricao,
                'tipo': rel.tipo,
            }
            for rel in obj.polegadas_permitidas.select_related('polegada').filter(ativo=True)
        ]

    def get_roscas_permitidas(self, obj: FamiliaProduto):
        return [
            {
                'id': rel.rosca_conexao_id,
                'codigo': rel.rosca_conexao.codigo,
                'descricao': rel.rosca_conexao.descricao,
                'padrao_da_familia': rel.padrao_da_familia,
            }
            for rel in obj.roscas_permitidas.select_related('rosca_conexao').filter(ativo=True)
        ]

    def get_schedules_permitidos(self, obj: FamiliaProduto):
        return [
            {
                'id': rel.schedule_id,
                'codigo_schedule': rel.schedule.codigo_schedule,
                'descricao': rel.schedule.descricao,
                'padrao_da_familia': rel.padrao_da_familia,
            }
            for rel in obj.schedules_permitidos.select_related('schedule').filter(ativo=True)
        ]

    def get_rosca_padrao_id(self, obj: FamiliaProduto):
        rel = obj.roscas_permitidas.filter(ativo=True, padrao_da_familia=True).first()
        return rel.rosca_conexao_id if rel else None

    def get_schedule_padrao_id(self, obj: FamiliaProduto):
        rel = obj.schedules_permitidos.filter(ativo=True, padrao_da_familia=True).first()
        return rel.schedule_id if rel else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['ncm_padrao'] = instance.ncm_padrao_id
        data['ncm_padrao_id'] = instance.ncm_padrao_id
        data['ncm_padrao_info'] = self.get_ncm_padrao_info(instance)
        return data


class FamiliaProdutoPolegadaPermitidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamiliaProdutoPolegadaPermitida
        fields = '__all__'


class FamiliaProdutoRoscaConexaoPermitidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamiliaProdutoRoscaConexaoPermitida
        fields = '__all__'


class FamiliaProdutoSchedulePermitidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamiliaProdutoSchedulePermitido
        fields = '__all__'


class ProdutoSerializer(serializers.ModelSerializer):
    preco_custo = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    preco_venda = serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=False)
    estoque_minimo = serializers.DecimalField(max_digits=14, decimal_places=3, coerce_to_string=False)

    familia_id = serializers.PrimaryKeyRelatedField(
        queryset=FamiliaProduto.objects.filter(ativo=True).exclude(
            tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
        ),
        source='familia',
        allow_null=True,
        required=False,
    )
    rosca_conexao_id = serializers.PrimaryKeyRelatedField(
        queryset=RoscaConexao.objects.filter(ativo=True),
        source='rosca_conexao',
        allow_null=True,
        required=False,
    )
    schedule_ref_id = serializers.PrimaryKeyRelatedField(
        queryset=ScheduleEspessura.objects.filter(ativo=True),
        source='schedule_ref',
        allow_null=True,
        required=False,
    )
    polegada_principal_ref_id = serializers.PrimaryKeyRelatedField(
        queryset=Polegada.objects.all(),
        source='polegada_principal_ref',
        allow_null=True,
        required=False,
    )
    polegada_secundaria_ref_id = serializers.PrimaryKeyRelatedField(
        queryset=Polegada.objects.all(),
        source='polegada_secundaria_ref',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Produto
        fields = (
            'id',
            'modo_codigo',
            'familia_id',
            'rosca_conexao_id',
            'schedule_ref_id',
            'polegada_principal_ref_id',
            'polegada_secundaria_ref_id',
            'figura',
            'sufixo',
            'schedule',
            'polegada_principal',
            'polegada_secundaria',
            'descricao',
            'material',
            'tipo_peca',
            'pressao_nominal',
            'norma',
            'conexao',
            'ncm',
            'unidade',
            'ncm_especifico',
            'unidade_especifica',
            'preco_custo',
            'preco_venda',
            'estoque_minimo',
            'codigo_completo',
            'tipo_controle_unidade',
            'tipo_fisico',
            'unidade_estoque',
            'unidade_venda_padrao',
            'unidade_compra_padrao',
            'unidade_fiscal',
            'unidades_venda_permitidas',
            'unidades_compra_permitidas',
            'observacoes_conversao',
            'comprimento_padrao_barra_m',
            'peso_por_metro_kg',
            'peso_por_peca_kg',
            'peso_por_chapa_kg',
            'densidade',
            'usa_conversao_dimensional',
        )

    def validate(self, attrs):
        inst = self.instance
        normalize_operational_fields(
            attrs,
            {
                'modo_codigo',
                'figura',
                'sufixo',
                'schedule',
                'polegada_principal',
                'polegada_secundaria',
                'descricao',
                'material',
                'tipo_peca',
                'pressao_nominal',
                'norma',
                'conexao',
                'ncm',
                'unidade',
                'ncm_especifico',
                'unidade_especifica',
                'codigo_completo',
                'tipo_controle_unidade',
                'tipo_fisico',
                'unidade_estoque',
                'unidade_venda_padrao',
                'unidade_compra_padrao',
                'unidade_fiscal',
                'observacoes_conversao',
            },
        )

        def pick(name: str):
            if name in attrs:
                return attrs[name]
            return getattr(inst, name, None) if inst else None

        modo = pick('modo_codigo') or Produto.ModoCodigo.LEGADO
        familia = pick('familia')
        codigo_in = to_operational_upper(pick('codigo_completo')) or ''

        if modo == Produto.ModoCodigo.MANUAL:
            if not codigo_in:
                raise serializers.ValidationError(
                    {'codigo_completo': 'Informe o código manual / fabricante.'},
                )
            if '...' in codigo_in or '..' in codigo_in:
                raise serializers.ValidationError({'codigo_completo': 'Código inválido (evite reticências ou segmentos vazios).'})
            qs = Produto.objects.exclude(pk=inst.pk) if inst else Produto.objects.all()
            if qs.filter(codigo_completo=codigo_in).exists():
                raise serializers.ValidationError({'codigo_completo': 'Já existe produto com este código.'})
            attrs['codigo_completo'] = codigo_in
            return attrs

        if modo == Produto.ModoCodigo.LEGADO:
            return attrs

        # INTERNO
        if not familia:
            raise serializers.ValidationError({'familia_id': 'Selecione a família / figura para código interno.'})

        if not familia.ativo:
            raise serializers.ValidationError({'familia_id': 'Família inativa.'})

        if familia.tipo_regra_codigo == FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE:
            raise serializers.ValidationError(
                {
                    'familia_id': 'Esta família é apenas para orientação; não gera código automático. '
                    'Use o modo "Código manual / fabricante" no produto.',
                },
            )

        req = flags_por_tipo_regra(familia.tipo_regra_codigo)
        rosca = pick('rosca_conexao')
        schedule = pick('schedule_ref')
        pp = pick('polegada_principal_ref')
        ps = pick('polegada_secundaria_ref')

        f = familia
        if req['usa_polegada_principal'] and not pp:
            raise serializers.ValidationError(
                {'polegada_principal_ref_id': 'Polegada principal obrigatória para esta família.'},
            )
        if req['usa_polegada_secundaria'] and not ps:
            raise serializers.ValidationError(
                {'polegada_secundaria_ref_id': 'Polegada secundária obrigatória para esta família.'},
            )
        if req['usa_rosca_conexao'] and rosca is None:
            raise serializers.ValidationError(
                {'rosca_conexao_id': 'Rosca / conexão obrigatória para esta família (inclua BSP/padrão se aplicável).'},
            )
        if req['usa_schedule'] and schedule is None:
            raise serializers.ValidationError(
                {'schedule_ref_id': 'Schedule / espessura obrigatório para esta família.'},
            )
        if not req['usa_rosca_conexao'] and rosca is not None:
            raise serializers.ValidationError({'rosca_conexao_id': 'Esta família não utiliza rosca / conexão.'})
        if not req['usa_schedule'] and schedule is not None:
            raise serializers.ValidationError({'schedule_ref_id': 'Esta família não utiliza schedule.'})
        if not req['usa_polegada_principal'] and pp is not None:
            raise serializers.ValidationError({'polegada_principal_ref_id': 'Esta família não utiliza polegada principal.'})
        if not req['usa_polegada_secundaria'] and ps is not None:
            raise serializers.ValidationError({'polegada_secundaria_ref_id': 'Esta família não utiliza polegada secundária.'})

        polegadas_rel = familia.polegadas_permitidas.filter(ativo=True)
        if req['usa_polegada_principal']:
            allowed_principal_ids = set(
                polegadas_rel.filter(tipo__in=[
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.PRINCIPAL,
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.AMBAS,
                ]).values_list('polegada_id', flat=True),
            )
            if not allowed_principal_ids:
                raise serializers.ValidationError(
                    {'polegada_principal_ref_id': 'Configure as polegadas permitidas desta família antes de criar produtos.'},
                )
            if pp and pp.id not in allowed_principal_ids:
                raise serializers.ValidationError(
                    {'polegada_principal_ref_id': f'A polegada {pp.descricao} não está permitida para esta família.'},
                )
        if req['usa_polegada_secundaria']:
            allowed_sec_ids = set(
                polegadas_rel.filter(tipo__in=[
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.SECUNDARIA,
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.AMBAS,
                ]).values_list('polegada_id', flat=True),
            )
            if not allowed_sec_ids:
                raise serializers.ValidationError(
                    {'polegada_secundaria_ref_id': 'Configure polegadas secundárias permitidas nesta família.'},
                )
            if ps and ps.id not in allowed_sec_ids:
                raise serializers.ValidationError(
                    {'polegada_secundaria_ref_id': f'A polegada {ps.descricao} não está permitida para esta família.'},
                )
        if req['usa_rosca_conexao']:
            allowed_rosc_ids = set(
                familia.roscas_permitidas.filter(ativo=True).values_list('rosca_conexao_id', flat=True),
            )
            if not allowed_rosc_ids:
                raise serializers.ValidationError(
                    {'rosca_conexao_id': 'Configure as roscas/conexões permitidas desta família antes de criar produtos.'},
                )
            if rosca and rosca.id not in allowed_rosc_ids:
                raise serializers.ValidationError(
                    {'rosca_conexao_id': f'A rosca/conexão {rosca.descricao} não está permitida para esta família.'},
                )
        if req['usa_schedule']:
            allowed_sched_ids = set(
                familia.schedules_permitidos.filter(ativo=True).values_list('schedule_id', flat=True),
            )
            if not allowed_sched_ids:
                raise serializers.ValidationError(
                    {'schedule_ref_id': 'Configure os schedules permitidos desta família antes de criar produtos.'},
                )
            if schedule and schedule.id not in allowed_sched_ids:
                raise serializers.ValidationError(
                    {'schedule_ref_id': f'O schedule {schedule.codigo_schedule} não está permitido para esta família.'},
                )

        codigo = montar_codigo_interno(f, rosca=rosca, schedule=schedule, polegada_principal=pp, polegada_secundaria=ps)
        if not codigo_interno_valido(codigo):
            raise serializers.ValidationError(
                {'non_field_errors': ['Código será gerado após preencher os campos obrigatórios da família.']},
            )

        qs = Produto.objects.exclude(pk=inst.pk) if inst else Produto.objects.all()
        if qs.filter(codigo_completo=codigo).exists():
            raise serializers.ValidationError({'non_field_errors': [f'Já existe produto com o código "{codigo}".']})

        attrs['codigo_completo'] = codigo
        # espelha nos campos texto para listagens / legado futuro
        attrs['figura'] = (f.codigo_figura or '').strip()
        attrs['sufixo'] = (rosca.codigo or '').strip() if rosca else ''
        attrs['schedule'] = (schedule.codigo_schedule or '').strip() if schedule else ''
        attrs['polegada_principal'] = pp.descricao if pp else ''
        attrs['polegada_secundaria'] = ps.descricao if ps else ''

        desc_merged = (attrs['descricao'] if 'descricao' in attrs else None)
        if desc_merged is None and inst:
            desc_merged = inst.descricao
        desc_merged = (desc_merged or '').strip()
        if not desc_merged:
            sug = montar_descricao_sugerida(f, rosca=rosca, schedule=schedule, polegada_principal=pp, polegada_secundaria=ps)
            if sug:
                attrs['descricao'] = sug

        ncm_m = (attrs['ncm'] if 'ncm' in attrs else (inst.ncm if inst else '')) or ''
        ncm_especifico = (attrs['ncm_especifico'] if 'ncm_especifico' in attrs else (inst.ncm_especifico if inst else '')) or ''
        if ncm_especifico.strip() and not ncm_m.strip():
            attrs['ncm'] = ncm_especifico.strip()
        mat_m = (attrs['material'] if 'material' in attrs else (inst.material if inst else '')) or ''
        if not mat_m.strip() and (familia.material_base or '').strip():
            attrs['material'] = familia.material_base.strip()
        press_m = (attrs['pressao_nominal'] if 'pressao_nominal' in attrs else (inst.pressao_nominal if inst else '')) or ''
        if not press_m.strip() and (familia.pressao_base or '').strip():
            attrs['pressao_nominal'] = familia.pressao_base.strip()
        norma_m = (attrs['norma'] if 'norma' in attrs else (inst.norma if inst else '')) or ''
        if not norma_m.strip() and (familia.norma_base or '').strip():
            attrs['norma'] = familia.norma_base.strip()
        unidade_eff = (attrs['unidade_especifica'] if 'unidade_especifica' in attrs else (inst.unidade_especifica if inst else '')) or ''
        if unidade_eff.strip():
            attrs['unidade'] = unidade_eff.strip()
        elif (familia.unidade_padrao or '').strip():
            attrs['unidade'] = familia.unidade_padrao.strip()
        if not (attrs.get('conexao') or '').strip() and (familia.conexao_base or '').strip():
            attrs['conexao'] = familia.conexao_base.strip()

        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError as e:
            if 'codigo_completo' in str(e).lower() or 'unique' in str(e).lower():
                raise serializers.ValidationError({'codigo_completo': 'Código já cadastrado.'}) from e
            raise

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except IntegrityError as e:
            if 'codigo_completo' in str(e).lower() or 'unique' in str(e).lower():
                raise serializers.ValidationError({'codigo_completo': 'Código já cadastrado.'}) from e
            raise

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('preco_custo', 'preco_venda', 'estoque_minimo'):
            if k in data and data[k] is not None:
                data[k] = float(Decimal(str(data[k])))
        data['familia_id'] = instance.familia_id
        data['rosca_conexao_id'] = instance.rosca_conexao_id
        data['schedule_ref_id'] = instance.schedule_ref_id
        data['polegada_principal_ref_id'] = instance.polegada_principal_ref_id
        data['polegada_secundaria_ref_id'] = instance.polegada_secundaria_ref_id
        ncm_efetivo = instance.get_ncm_efetivo()
        data['ncm_efetivo'] = (
            {
                'id': getattr(ncm_efetivo, 'id', None),
                'codigo': getattr(ncm_efetivo, 'codigo', ''),
                'descricao': getattr(ncm_efetivo, 'descricao', ''),
            }
            if ncm_efetivo
            else None
        )
        data['unidade_efetiva'] = (instance.unidade_especifica or '').strip() or (instance.unidade or '').strip()
        data['ncm_origem'] = instance.get_ncm_origem()
        data['origem_ncm'] = instance.get_ncm_origem()
        data['origem_unidade'] = 'produto' if (instance.unidade_especifica or '').strip() else 'familia'
        data['tipo_controle_unidade_efetivo'] = instance.get_tipo_controle_unidade_efetivo()
        data['tipo_fisico_efetivo'] = instance.get_tipo_fisico_efetivo()
        data['unidade_estoque_efetiva'] = instance.get_unidade_estoque_efetiva()
        data['unidade_venda_efetiva'] = instance.get_unidade_venda_efetiva()
        data['unidade_compra_efetiva'] = instance.get_unidade_compra_efetiva()
        data['unidade_fiscal_efetiva'] = instance.get_unidade_fiscal_efetiva()
        data['unidades_venda_permitidas_efetivas'] = instance.get_unidades_venda_permitidas_efetivas()
        data['usa_conversao_dimensional_efetivo'] = instance.get_usa_conversao_dimensional_efetivo()
        data['alertas'] = (
            ['Este produto usa NCM diferente do padrão da família.']
            if (instance.ncm_especifico or '').strip()
            else []
        )
        return data


class PreviewCodigoSerializer(serializers.Serializer):
    familia_id = serializers.PrimaryKeyRelatedField(queryset=FamiliaProduto.objects.filter(ativo=True))
    rosca_conexao_id = serializers.PrimaryKeyRelatedField(
        queryset=RoscaConexao.objects.filter(ativo=True),
        allow_null=True,
        required=False,
    )
    schedule_ref_id = serializers.PrimaryKeyRelatedField(
        queryset=ScheduleEspessura.objects.filter(ativo=True),
        allow_null=True,
        required=False,
    )
    polegada_principal_ref_id = serializers.PrimaryKeyRelatedField(
        queryset=Polegada.objects.all(),
        allow_null=True,
        required=False,
    )
    polegada_secundaria_ref_id = serializers.PrimaryKeyRelatedField(
        queryset=Polegada.objects.all(),
        allow_null=True,
        required=False,
    )

    def validate(self, attrs):
        f: FamiliaProduto = attrs['familia_id']
        if f.tipo_regra_codigo == FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE:
            attrs['_codigo'] = ''
            attrs['_descricao'] = ''
            attrs['_mensagem'] = 'Esta família não gera código automático. Use o produto em modo "Código manual / fabricante".'
            return attrs

        req = flags_por_tipo_regra(f.tipo_regra_codigo)
        rosca = attrs.get('rosca_conexao_id')
        schedule = attrs.get('schedule_ref_id')
        pp = attrs.get('polegada_principal_ref_id')
        ps = attrs.get('polegada_secundaria_ref_id')

        if req['usa_polegada_principal'] and not pp:
            raise serializers.ValidationError({'polegada_principal_ref_id': 'Obrigatório para esta família.'})
        if req['usa_polegada_secundaria'] and not ps:
            raise serializers.ValidationError({'polegada_secundaria_ref_id': 'Obrigatório para esta família.'})
        if req['usa_rosca_conexao'] and rosca is None:
            raise serializers.ValidationError({'rosca_conexao_id': 'Obrigatório para esta família.'})
        if req['usa_schedule'] and schedule is None:
            raise serializers.ValidationError({'schedule_ref_id': 'Obrigatório para esta família.'})
        if not req['usa_rosca_conexao'] and rosca is not None:
            raise serializers.ValidationError({'rosca_conexao_id': 'Esta família não utiliza rosca/conexão.'})
        if not req['usa_schedule'] and schedule is not None:
            raise serializers.ValidationError({'schedule_ref_id': 'Esta família não utiliza schedule.'})

        polegadas_rel = f.polegadas_permitidas.filter(ativo=True)
        if req['usa_polegada_principal']:
            allowed_pp = set(
                polegadas_rel.filter(tipo__in=[
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.PRINCIPAL,
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.AMBAS,
                ]).values_list('polegada_id', flat=True),
            )
            if not allowed_pp:
                raise serializers.ValidationError(
                    {'polegada_principal_ref_id': 'Configure as polegadas permitidas desta família antes de criar produtos.'},
                )
            if pp and pp.id not in allowed_pp:
                raise serializers.ValidationError({'polegada_principal_ref_id': f'A polegada {pp.descricao} não está permitida para esta família.'})
        if req['usa_polegada_secundaria']:
            allowed_ps = set(
                polegadas_rel.filter(tipo__in=[
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.SECUNDARIA,
                    FamiliaProdutoPolegadaPermitida.TipoPolegada.AMBAS,
                ]).values_list('polegada_id', flat=True),
            )
            if not allowed_ps:
                raise serializers.ValidationError(
                    {'polegada_secundaria_ref_id': 'Configure polegadas secundárias permitidas nesta família.'},
                )
            if ps and ps.id not in allowed_ps:
                raise serializers.ValidationError({'polegada_secundaria_ref_id': f'A polegada {ps.descricao} não está permitida para esta família.'})
        if req['usa_rosca_conexao']:
            allowed_rosca = set(f.roscas_permitidas.filter(ativo=True).values_list('rosca_conexao_id', flat=True))
            if not allowed_rosca:
                raise serializers.ValidationError({'rosca_conexao_id': 'Configure roscas/conexões permitidas desta família.'})
            if rosca and rosca.id not in allowed_rosca:
                raise serializers.ValidationError({'rosca_conexao_id': f'A rosca/conexão {rosca.descricao} não está permitida para esta família.'})
        if req['usa_schedule']:
            allowed_sched = set(f.schedules_permitidos.filter(ativo=True).values_list('schedule_id', flat=True))
            if not allowed_sched:
                raise serializers.ValidationError({'schedule_ref_id': 'Configure schedules permitidos desta família.'})
            if schedule and schedule.id not in allowed_sched:
                raise serializers.ValidationError({'schedule_ref_id': f'O schedule {schedule.codigo_schedule} não está permitido para esta família.'})

        codigo = montar_codigo_interno(f, rosca=rosca, schedule=schedule, polegada_principal=pp, polegada_secundaria=ps)
        if not codigo_interno_valido(codigo):
            attrs['_codigo'] = ''
            attrs['_descricao'] = montar_descricao_sugerida(f, rosca=rosca, schedule=schedule, polegada_principal=pp, polegada_secundaria=ps)
            attrs['_mensagem'] = 'Código será gerado após preencher os campos obrigatórios da família.'
            attrs['_ncm_efetivo'] = (f.ncm_padrao.codigo if f.ncm_padrao_id else '')
            attrs['_unidade_efetiva'] = (f.unidade_padrao or '').strip()
            attrs['_origem_ncm'] = 'familia'
            attrs['_origem_unidade'] = 'familia'
            attrs['_mensagens'] = [attrs['_mensagem']]
            return attrs

        attrs['_codigo'] = codigo
        attrs['_descricao'] = montar_descricao_sugerida(f, rosca=rosca, schedule=schedule, polegada_principal=pp, polegada_secundaria=ps)
        attrs['_mensagem'] = ''
        attrs['_ncm_efetivo'] = (f.ncm_padrao.codigo if f.ncm_padrao_id else '')
        attrs['_unidade_efetiva'] = (f.unidade_padrao or '').strip()
        attrs['_origem_ncm'] = 'familia'
        attrs['_origem_unidade'] = 'familia'
        attrs['_mensagens'] = []
        return attrs


class ConverterMedidaSerializer(serializers.Serializer):
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.select_related('familia').all(), source='produto')
    quantidade = serializers.DecimalField(max_digits=14, decimal_places=3)
    unidade_origem = serializers.CharField(max_length=16)
    unidade_destino = serializers.CharField(max_length=16)

    def validate(self, attrs):
        produto = attrs['produto']
        unidade_origem = attrs['unidade_origem'].upper()
        unidade_destino = attrs['unidade_destino'].upper()
        permitidas = set(produto.get_unidades_venda_permitidas_efetivas() or [])
        if permitidas:
            if unidade_origem not in permitidas:
                raise serializers.ValidationError({'unidade_origem': 'Unidade de origem não permitida para este produto.'})
            if unidade_destino not in permitidas:
                raise serializers.ValidationError({'unidade_destino': 'Unidade de destino não permitida para este produto.'})
        try:
            resultado = converter_quantidade_produto(produto, attrs['quantidade'], unidade_origem, unidade_destino)
        except ConversaoErro as exc:
            raise serializers.ValidationError({'mensagem': str(exc)}) from exc
        attrs['_resultado'] = resultado
        return attrs
