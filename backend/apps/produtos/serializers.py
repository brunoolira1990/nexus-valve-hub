from decimal import Decimal

from django.db import IntegrityError
from rest_framework import serializers

from apps.produtos.codigo_produto import (
    codigo_interno_valido,
    montar_codigo_interno,
    montar_descricao_sugerida,
)
from apps.produtos.dimensional_regra import (
    comprimento_mm_efetivo,
    requisitos_efetivos_produto,
    tipo_medida_esperado_por_campo,
    validar_campos_obrigatorios_produto_interno,
    validar_tipo_dimensional_x_regra,
)
from apps.produtos.familia_regra import aplicar_flags_derivadas_no_dict
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


def _decimal_from_dim(raw):
    if raw in (None, ''):
        return None
    if isinstance(raw, str):
        raw = raw.strip().replace(',', '.')
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _validar_dimensional_materiais(familia: FamiliaProduto, dims: dict) -> dict[str, str]:
    td = familia.tipo_dimensional
    errs: dict[str, str] = {}
    reqs: dict[str, list[str]] = {
        FamiliaProduto.TipoDimensional.CHAPA_MM: ['espessura_mm', 'largura_mm', 'comprimento_mm'],
        FamiliaProduto.TipoDimensional.CHAPA_FURO_MM: ['furo_mm', 'espessura_mm', 'largura_mm', 'comprimento_mm'],
        FamiliaProduto.TipoDimensional.METALON_MM: ['altura_mm', 'largura_mm', 'espessura_mm'],
        FamiliaProduto.TipoDimensional.PERFIL_RETANGULAR_MM: ['altura_mm', 'largura_mm', 'espessura_mm'],
        FamiliaProduto.TipoDimensional.BARRA_CHATA_MM: ['largura_mm', 'espessura_mm'],
        FamiliaProduto.TipoDimensional.CANTONEIRA_MM: ['aba_mm', 'espessura_mm'],
    }
    labels = {
        'furo_mm': 'Informe o Furo em mm.',
        'espessura_mm': 'Informe a Espessura em mm.',
        'largura_mm': 'Informe a Largura em mm.',
        'comprimento_mm': 'Informe o Comprimento em mm.',
        'altura_mm': 'Informe a Altura em mm.',
        'aba_mm': 'Informe a Aba em mm.',
    }
    for key in reqs.get(td, []):
        if _decimal_from_dim((dims or {}).get(key)) is None:
            errs[f'dimensoes_json.{key}'] = labels[key]
    if td == FamiliaProduto.TipoDimensional.CANTONEIRA_POLEGADA:
        if not (dims or {}).get('aba_polegada_ref_id'):
            errs['dim_aba_polegada_ref_id'] = 'Informe a Aba em polegada.'
        if not (dims or {}).get('espessura_polegada_ref_id'):
            errs['dim_espessura_polegada_ref_id'] = 'Informe a Espessura em polegada.'
    if td == FamiliaProduto.TipoDimensional.DIMENSIONAL_LIVRE_CONTROLADO:
        codigo = to_operational_upper(str((dims or {}).get('dimensao_codigo') or '').strip())
        desc = to_operational_upper(str((dims or {}).get('dimensao_descricao') or '').strip())
        if not codigo:
            errs['dimensao_codigo'] = 'Informe o código dimensional.'
        elif not all(c.isalnum() or c in {'_', '-', '.', 'X', 'P'} for c in codigo):
            errs['dimensao_codigo'] = 'Use apenas letras, números, X, P, ponto, hífen ou underscore.'
        if not desc:
            errs['dimensao_descricao'] = 'Informe a descrição dimensional.'
    return errs


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
        normalize_operational_fields(attrs, {'codigo', 'codigo_oficial', 'descricao', 'origem', 'observacoes', 'tipo_medida'})
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
        tipo = obj.tipo_medida or ''
        mm = f' — {obj.valor_mm} mm' if obj.valor_mm is not None else ''
        return f'{tipo} {obj.codigo_oficial} — {obj.descricao}{mm}'.strip()


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
        normalize_operational_fields(attrs, {'codigo_schedule', 'codigo', 'descricao', 'aplicacao', 'observacoes'})
        if not attrs.get('codigo_schedule'):
            attrs['codigo_schedule'] = attrs.get('codigo') or getattr(self.instance, 'codigo_schedule', '')
        if not attrs.get('codigo'):
            attrs['codigo'] = attrs.get('codigo_schedule') or getattr(self.instance, 'codigo_schedule', '')
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
                'tipo_dimensional',
                'categoria_produto',
            },
        )
        tipo = attrs.get('tipo_regra_codigo')
        if tipo is None and inst is not None:
            tipo = inst.tipo_regra_codigo
        if tipo is None:
            tipo = FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA
            attrs['tipo_regra_codigo'] = tipo
        aplicar_flags_derivadas_no_dict(attrs, tipo)

        td = attrs.get('tipo_dimensional')
        if td is None and inst is not None:
            td = inst.tipo_dimensional
        if td is None:
            td = FamiliaProduto.TipoDimensional.SIMPLES
            attrs['tipo_dimensional'] = td

        msg = validar_tipo_dimensional_x_regra(tipo_dimensional=td, tipo_regra_codigo=tipo)
        if msg:
            raise serializers.ValidationError({'tipo_dimensional': msg})
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
                'codigo': rel.schedule.codigo,
                'descricao': rel.schedule.descricao,
                'aplicacao': rel.schedule.aplicacao,
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

    def get_requisitos_produto(self, obj: FamiliaProduto):
        return requisitos_efetivos_produto(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['ncm_padrao'] = instance.ncm_padrao_id
        data['ncm_padrao_id'] = instance.ncm_padrao_id
        data['ncm_padrao_info'] = self.get_ncm_padrao_info(instance)
        data['requisitos_produto'] = self.get_requisitos_produto(instance)
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
            'od_mm',
            'espessura_mm',
            'comprimento_mm',
            'dimensoes_json',
            'dim_espessura_mm',
            'dim_largura_mm',
            'dim_comprimento_mm',
            'dim_altura_mm',
            'dim_furo_mm',
            'dim_aba_mm',
            'dim_aba_polegada_ref',
            'dim_espessura_polegada_ref',
            'dimensao_codigo',
            'dimensao_descricao',
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
                'dimensao_codigo',
                'dimensao_descricao',
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

        req = requisitos_efetivos_produto(familia)
        rosca = pick('rosca_conexao')
        schedule = pick('schedule_ref')
        pp = pick('polegada_principal_ref')
        ps = pick('polegada_secundaria_ref')
        dim_aba_pol = pick('dim_aba_polegada_ref')
        dim_esp_pol = pick('dim_espessura_polegada_ref')
        od_mm = pick('od_mm')
        esp_mm = pick('espessura_mm')
        comp_in = pick('comprimento_mm')
        dimensoes_json = pick('dimensoes_json') or {}
        dim_values = {
            **(dimensoes_json if isinstance(dimensoes_json, dict) else {}),
            'espessura_mm': pick('dim_espessura_mm'),
            'largura_mm': pick('dim_largura_mm'),
            'comprimento_mm': pick('dim_comprimento_mm'),
            'altura_mm': pick('dim_altura_mm'),
            'furo_mm': pick('dim_furo_mm'),
            'aba_mm': pick('dim_aba_mm'),
            'aba_polegada_ref_id': pick('dim_aba_polegada_ref').id if pick('dim_aba_polegada_ref') else None,
            'espessura_polegada_ref_id': pick('dim_espessura_polegada_ref').id if pick('dim_espessura_polegada_ref') else None,
            'dimensao_codigo': pick('dimensao_codigo'),
            'dimensao_descricao': pick('dimensao_descricao'),
        }
        pp_eff = dim_aba_pol if familia.tipo_dimensional == FamiliaProduto.TipoDimensional.CANTONEIRA_POLEGADA else pp
        ps_eff = dim_esp_pol if familia.tipo_dimensional == FamiliaProduto.TipoDimensional.CANTONEIRA_POLEGADA else ps
        comp_resolved = comprimento_mm_efetivo(comprimento_mm=comp_in, familia=familia)

        f = familia
        ferr = validar_campos_obrigatorios_produto_interno(
            familia,
            rosca=rosca,
            schedule=schedule,
            polegada_principal=pp,
            polegada_secundaria=ps,
            od_mm=od_mm,
            espessura_mm=esp_mm,
            comprimento_mm_resolvido=comp_resolved,
        )
        if ferr:
            raise serializers.ValidationError({k: [v] for k, v in ferr.items()})
        ferr_dim = _validar_dimensional_materiais(familia, dim_values)
        if ferr_dim:
            raise serializers.ValidationError({k: [v] for k, v in ferr_dim.items()})

        if comp_in is None and comp_resolved is not None and familia.comprimento_padrao_barra_m:
            attrs['comprimento_mm'] = comp_resolved

        if not req['usa_rosca_conexao'] and rosca is not None:
            raise serializers.ValidationError({'rosca_conexao_id': 'Esta família não utiliza rosca / conexão.'})
        if not req['usa_schedule'] and schedule is not None:
            raise serializers.ValidationError({'schedule_ref_id': 'Esta família não utiliza schedule (OD não é NPS/SCH).'})
        if not req['usa_polegada_principal'] and pp is not None:
            raise serializers.ValidationError({'polegada_principal_ref_id': 'Esta família não utiliza esta medida como polegada principal.'})
        if not req['usa_polegada_secundaria'] and ps is not None:
            raise serializers.ValidationError({'polegada_secundaria_ref_id': 'Esta família não utiliza polegada secundária.'})
        if not req['exige_od_mm'] and od_mm is not None:
            raise serializers.ValidationError({'od_mm': 'Esta família não utiliza OD em mm no produto.'})
        if not req['exige_espessura_mm'] and esp_mm is not None:
            raise serializers.ValidationError({'espessura_mm': 'Esta família não utiliza espessura em mm no produto.'})
        if not req['exige_comprimento_mm'] and pick('comprimento_mm') is not None:
            raise serializers.ValidationError({'comprimento_mm': 'Esta família não utiliza comprimento em mm no produto.'})

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
        expected_types = tipo_medida_esperado_por_campo(familia)
        if pp is not None:
            expected_principal = expected_types.get('polegada_principal_ref_id')
            if expected_principal and pp.tipo_medida != expected_principal:
                msg = 'Informe a medida OD.' if expected_principal == Polegada.TipoMedida.OD else 'Informe a medida NPS.'
                raise serializers.ValidationError({'polegada_principal_ref_id': msg})
        if ps is not None:
            expected_sec = expected_types.get('polegada_secundaria_ref_id')
            if expected_sec and ps.tipo_medida != expected_sec:
                if familia.tipo_dimensional == FamiliaProduto.TipoDimensional.OD_POLEGADA_X_ROSCA:
                    msg = 'Informe a medida da rosca.'
                elif expected_sec == Polegada.TipoMedida.OD:
                    msg = 'Informe a medida OD.'
                else:
                    msg = 'Informe a medida NPS.'
                raise serializers.ValidationError({'polegada_secundaria_ref_id': msg})
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

        codigo = montar_codigo_interno(
            f,
            rosca=rosca,
            schedule=schedule,
            polegada_principal=pp_eff,
            polegada_secundaria=ps_eff,
            od_mm=od_mm,
            espessura_mm=esp_mm,
            dimensoes=dimensoes_json if isinstance(dimensoes_json, dict) else {},
        )
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
            sug = montar_descricao_sugerida(
                f,
                rosca=rosca,
                schedule=schedule,
                polegada_principal=pp_eff,
                polegada_secundaria=ps_eff,
                od_mm=od_mm,
                espessura_mm=esp_mm,
                comprimento_mm=comp_resolved,
                dimensoes=dimensoes_json if isinstance(dimensoes_json, dict) else {},
            )
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
        for k in ('od_mm', 'espessura_mm', 'comprimento_mm'):
            if k in data and data[k] is not None:
                data[k] = float(Decimal(str(data[k])))
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
    od_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    espessura_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    comprimento_mm = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True, required=False)
    dimensoes_json = serializers.JSONField(required=False)
    dim_espessura_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    dim_largura_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    dim_comprimento_mm = serializers.DecimalField(max_digits=14, decimal_places=3, allow_null=True, required=False)
    dim_altura_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    dim_furo_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    dim_aba_mm = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True, required=False)
    dim_aba_polegada_ref_id = serializers.PrimaryKeyRelatedField(queryset=Polegada.objects.filter(tipo_medida=Polegada.TipoMedida.OD), allow_null=True, required=False)
    dim_espessura_polegada_ref_id = serializers.PrimaryKeyRelatedField(queryset=Polegada.objects.filter(tipo_medida=Polegada.TipoMedida.OD), allow_null=True, required=False)
    dimensao_codigo = serializers.CharField(max_length=64, allow_blank=True, required=False)
    dimensao_descricao = serializers.CharField(max_length=256, allow_blank=True, required=False)

    def validate(self, attrs):
        f: FamiliaProduto = attrs['familia_id']
        if f.tipo_regra_codigo == FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE:
            attrs['_codigo'] = ''
            attrs['_descricao'] = ''
            attrs['_mensagem'] = 'Esta família não gera código automático. Use o produto em modo "Código manual / fabricante".'
            return attrs

        req = requisitos_efetivos_produto(f)
        rosca = attrs.get('rosca_conexao_id')
        schedule = attrs.get('schedule_ref_id')
        pp = attrs.get('polegada_principal_ref_id')
        ps = attrs.get('polegada_secundaria_ref_id')
        dim_aba_pol = attrs.get('dim_aba_polegada_ref_id')
        dim_esp_pol = attrs.get('dim_espessura_polegada_ref_id')
        od_mm = attrs.get('od_mm')
        esp_mm = attrs.get('espessura_mm')
        comp_in = attrs.get('comprimento_mm')
        dimensoes_json = attrs.get('dimensoes_json') or {}
        dim_values = {
            **(dimensoes_json if isinstance(dimensoes_json, dict) else {}),
            'espessura_mm': attrs.get('dim_espessura_mm'),
            'largura_mm': attrs.get('dim_largura_mm'),
            'comprimento_mm': attrs.get('dim_comprimento_mm'),
            'altura_mm': attrs.get('dim_altura_mm'),
            'furo_mm': attrs.get('dim_furo_mm'),
            'aba_mm': attrs.get('dim_aba_mm'),
            'aba_polegada_ref_id': attrs.get('dim_aba_polegada_ref_id').id if attrs.get('dim_aba_polegada_ref_id') else None,
            'espessura_polegada_ref_id': attrs.get('dim_espessura_polegada_ref_id').id if attrs.get('dim_espessura_polegada_ref_id') else None,
            'dimensao_codigo': attrs.get('dimensao_codigo'),
            'dimensao_descricao': attrs.get('dimensao_descricao'),
        }
        pp_eff = dim_aba_pol if f.tipo_dimensional == FamiliaProduto.TipoDimensional.CANTONEIRA_POLEGADA else pp
        ps_eff = dim_esp_pol if f.tipo_dimensional == FamiliaProduto.TipoDimensional.CANTONEIRA_POLEGADA else ps
        comp_resolved = comprimento_mm_efetivo(comprimento_mm=comp_in, familia=f)

        ferr = validar_campos_obrigatorios_produto_interno(
            f,
            rosca=rosca,
            schedule=schedule,
            polegada_principal=pp,
            polegada_secundaria=ps,
            od_mm=od_mm,
            espessura_mm=esp_mm,
            comprimento_mm_resolvido=comp_resolved,
        )
        if ferr:
            raise serializers.ValidationError({k: [v] for k, v in ferr.items()})
        ferr_dim = _validar_dimensional_materiais(f, dim_values)
        if ferr_dim:
            raise serializers.ValidationError({k: [v] for k, v in ferr_dim.items()})

        if not req['usa_rosca_conexao'] and rosca is not None:
            raise serializers.ValidationError({'rosca_conexao_id': 'Esta família não utiliza rosca/conexão.'})
        if not req['usa_schedule'] and schedule is not None:
            raise serializers.ValidationError({'schedule_ref_id': 'Esta família não utiliza schedule.'})
        if not req['usa_polegada_principal'] and pp is not None:
            raise serializers.ValidationError({'polegada_principal_ref_id': 'Polegada principal não aplicável.'})
        if not req['usa_polegada_secundaria'] and ps is not None:
            raise serializers.ValidationError({'polegada_secundaria_ref_id': 'Polegada secundária não aplicável.'})
        if not req['exige_od_mm'] and od_mm is not None:
            raise serializers.ValidationError({'od_mm': 'OD em mm não aplicável.'})
        if not req['exige_espessura_mm'] and esp_mm is not None:
            raise serializers.ValidationError({'espessura_mm': 'Espessura em mm não aplicável.'})
        if not req['exige_comprimento_mm'] and comp_in is not None:
            raise serializers.ValidationError({'comprimento_mm': 'Comprimento em mm não aplicável.'})

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
        expected_types = tipo_medida_esperado_por_campo(f)
        if pp is not None:
            expected_principal = expected_types.get('polegada_principal_ref_id')
            if expected_principal and pp.tipo_medida != expected_principal:
                msg = 'Informe a medida OD.' if expected_principal == Polegada.TipoMedida.OD else 'Informe a medida NPS.'
                raise serializers.ValidationError({'polegada_principal_ref_id': msg})
        if ps is not None:
            expected_sec = expected_types.get('polegada_secundaria_ref_id')
            if expected_sec and ps.tipo_medida != expected_sec:
                if f.tipo_dimensional == FamiliaProduto.TipoDimensional.OD_POLEGADA_X_ROSCA:
                    msg = 'Informe a medida da rosca.'
                elif expected_sec == Polegada.TipoMedida.OD:
                    msg = 'Informe a medida OD.'
                else:
                    msg = 'Informe a medida NPS.'
                raise serializers.ValidationError({'polegada_secundaria_ref_id': msg})
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

        codigo = montar_codigo_interno(
            f,
            rosca=rosca,
            schedule=schedule,
            polegada_principal=pp_eff,
            polegada_secundaria=ps_eff,
            od_mm=od_mm,
            espessura_mm=esp_mm,
            dimensoes=dimensoes_json if isinstance(dimensoes_json, dict) else {},
        )
        desc_kwargs = dict(
            rosca=rosca,
            schedule=schedule,
            polegada_principal=pp_eff,
            polegada_secundaria=ps_eff,
            od_mm=od_mm,
            espessura_mm=esp_mm,
            comprimento_mm=comp_resolved,
            dimensoes=dimensoes_json if isinstance(dimensoes_json, dict) else {},
        )
        if not codigo_interno_valido(codigo):
            attrs['_codigo'] = ''
            attrs['_descricao'] = montar_descricao_sugerida(f, **desc_kwargs)
            attrs['_mensagem'] = 'Código será gerado após preencher os campos obrigatórios da família.'
            attrs['_ncm_efetivo'] = (f.ncm_padrao.codigo if f.ncm_padrao_id else '')
            attrs['_unidade_efetiva'] = (f.unidade_padrao or '').strip()
            attrs['_origem_ncm'] = 'familia'
            attrs['_origem_unidade'] = 'familia'
            attrs['_mensagens'] = [attrs['_mensagem']]
            return attrs

        attrs['_codigo'] = codigo
        attrs['_descricao'] = montar_descricao_sugerida(f, **desc_kwargs)
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
