from django.db.models import Count
from rest_framework import serializers

from apps.cadastros.models import Empresa, Fornecedor
from apps.fiscal.nfe_cbenef_sp import normalizar_codigo_beneficio_icms
from apps.produtos.models import Produto

from .cenario_fiscal_entrada import gerar_label_configuracao_fiscal, label_escopo
from .cenario_fiscal_saida import gerar_label_regra_fiscal_saida, label_escopo_saida
from .reforma_tributaria_config import normalizar_reforma_tributaria, resumo_reforma_tributaria
from .recomendacoes_nfe_config import (
    contar_recomendacoes_nfe,
    normalizar_recomendacoes_nfe,
    recomendacoes_nfe_preenchidas,
)
from .models import (
    CenarioFiscalEntrada,
    CenarioFiscalEntradaEscopo,
    CenarioFiscalSaida,
    CenarioFiscalSaidaEscopo,
    RegraFiscal,
    RegraFiscalEntrada,
    RegraFiscalSaida,
)


class RegraFiscalSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegraFiscal
        fields = '__all__'

    def validate_cfop(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Informe o CFOP.')
        return value.strip()

    def validate_operacao(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Informe o tipo de operação.')
        return value

    def validate_cst_icms(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Informe o CST/CSOSN de ICMS.')
        return value.strip()

    def validate_ncm(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Informe o NCM.')
        return value.strip()


class CenarioFiscalEntradaEscopoSerializer(serializers.ModelSerializer):
    cenario = serializers.PrimaryKeyRelatedField(read_only=True)
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
        allow_null=True,
        required=False,
    )
    configuracoes_count = serializers.IntegerField(read_only=True, default=0)
    label = serializers.SerializerMethodField()

    class Meta:
        model = CenarioFiscalEntradaEscopo
        fields = (
            'id',
            'cenario',
            'tipo_escopo',
            'ncm',
            'produto_id',
            'prioridade_escopo',
            'ativo',
            'configuracoes_count',
            'label',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def get_label(self, obj: CenarioFiscalEntradaEscopo) -> str:
        return label_escopo(obj)

    def validate(self, attrs):
        inst = self.instance
        cenario = attrs.get('cenario') or (inst.cenario if inst else None)
        tipo = attrs.get('tipo_escopo') or (inst.tipo_escopo if inst else '')
        produto = attrs.get('produto') if 'produto' in attrs else (inst.produto if inst else None)
        ncm = (attrs.get('ncm') if 'ncm' in attrs else (inst.ncm if inst else '')) or ''
        ncm = ncm.strip()

        if tipo == CenarioFiscalEntradaEscopo.TipoEscopo.PRODUTO and not produto:
            raise serializers.ValidationError({'produto_id': 'Informe o produto para escopo PRODUTO.'})
        if tipo in (
            CenarioFiscalEntradaEscopo.TipoEscopo.NCM,
            CenarioFiscalEntradaEscopo.TipoEscopo.NCM_PREFIXO,
        ) and not ncm:
            raise serializers.ValidationError({'ncm': 'Informe o NCM para este escopo.'})
        if tipo == CenarioFiscalEntradaEscopo.TipoEscopo.GERAL:
            attrs['ncm'] = ''
            attrs['produto'] = None
        return attrs


class CenarioFiscalEntradaSerializer(serializers.ModelSerializer):
    empresa_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source='empresa',
        allow_null=True,
        required=False,
    )
    total_escopos = serializers.IntegerField(read_only=True)
    total_configuracoes = serializers.IntegerField(read_only=True)

    class Meta:
        model = CenarioFiscalEntrada
        fields = (
            'id',
            'nome',
            'empresa_id',
            'regime_tributario',
            'ativo',
            'padrao',
            'observacoes',
            'total_escopos',
            'total_configuracoes',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em', 'total_escopos', 'total_configuracoes')


class CenarioFiscalEntradaDetailSerializer(CenarioFiscalEntradaSerializer):
    escopos = serializers.SerializerMethodField()

    class Meta(CenarioFiscalEntradaSerializer.Meta):
        fields = CenarioFiscalEntradaSerializer.Meta.fields + ('escopos',)

    def get_escopos(self, obj: CenarioFiscalEntrada):
        qs = (
            obj.escopos.annotate(configuracoes_count=Count('configuracoes'))
            .order_by('tipo_escopo', 'ncm', 'produto_id', 'id')
        )
        return CenarioFiscalEntradaEscopoSerializer(qs, many=True).data


class RegraFiscalEntradaSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
        allow_null=True,
        required=False,
    )
    fornecedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(),
        source='fornecedor',
        allow_null=True,
        required=False,
    )
    cenario_id = serializers.PrimaryKeyRelatedField(
        queryset=CenarioFiscalEntrada.objects.all(),
        source='cenario',
        allow_null=True,
        required=False,
    )
    escopo_id = serializers.PrimaryKeyRelatedField(
        queryset=CenarioFiscalEntradaEscopo.objects.all(),
        source='escopo',
        allow_null=True,
        required=False,
    )
    label_configuracao = serializers.SerializerMethodField()
    incompleta = serializers.SerializerMethodField()
    pendencias_fiscais = serializers.SerializerMethodField()

    class Meta:
        model = RegraFiscalEntrada
        fields = (
            'id',
            'cenario_id',
            'escopo_id',
            'nome',
            'codigo',
            'ativo',
            'prioridade',
            'cfop',
            'cfop_origem',
            'cfop_entrada',
            'descricao_cenario',
            'label_configuracao',
            'incompleta',
            'pendencias_fiscais',
            'ncm',
            'ncm_prefixo',
            'uf_origem',
            'uf_destino',
            'tipo_operacao_fiscal',
            'produto_id',
            'fornecedor_id',
            'cst_icms_esperado',
            'csosn_esperado',
            'cst_pis_esperado',
            'cst_cofins_esperado',
            'cst_ipi_esperado',
            'modalidade_bc_icms',
            'aliquota_icms',
            'reducao_bc_icms',
            'motivo_desoneracao_icms',
            'codigo_beneficio_icms',
            'icms_st_aplicavel',
            'cst_icms_st_esperado',
            'aliquota_icms_st',
            'mva_st',
            'reducao_bc_st',
            'fcp_aplicavel',
            'aliquota_fcp',
            'aliquota_fcp_st',
            'reducao_bc_fcp',
            'valor_fcp_unidade',
            'reforma_tributaria',
            'tipo_calculo_ipi',
            'aliquota_ipi',
            'valor_ipi_unidade',
            'enquadramento_ipi',
            'tipo_calculo_pis',
            'aliquota_pis',
            'reducao_base_pis',
            'valor_minimo_pis_unidade',
            'aliquota_pis_st',
            'tipo_calculo_cofins',
            'aliquota_cofins',
            'reducao_base_cofins',
            'valor_minimo_cofins_unidade',
            'aliquota_cofins_st',
            'movimenta_estoque',
            'exige_certificado_fornecedor',
            'permite_credito_fiscal',
            'severidade',
            'mensagem_padrao',
            'observacoes',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def get_label_configuracao(self, obj: RegraFiscalEntrada) -> str:
        return gerar_label_configuracao_fiscal(obj)

    def _regime_empresa(self) -> str:
        empresa = Empresa.objects.order_by('pk').first()
        return (empresa.regime_tributario or '').strip() if empresa else ''

    def get_incompleta(self, obj: RegraFiscalEntrada) -> bool:
        if not obj.ativo:
            return False
        from .regras_fiscais_minimas import regra_entrada_esta_incompleta

        return regra_entrada_esta_incompleta(obj, self._regime_empresa())

    def get_pendencias_fiscais(self, obj: RegraFiscalEntrada) -> list[str]:
        from .regras_fiscais_minimas import pendencias_regra_entrada_incompleta

        return pendencias_regra_entrada_incompleta(obj, self._regime_empresa())

    def validate_reforma_tributaria(self, value):
        if value in (None, '', {}):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError('reforma_tributaria deve ser um objeto JSON.')
        return normalizar_reforma_tributaria(value)

    def validate(self, attrs):
        inst = self.instance

        def val(key, default=''):
            if key in attrs:
                v = attrs[key]
                return (v or '').strip() if isinstance(v, str) else v
            if inst:
                return getattr(inst, key, default)
            return default

        cfop_origem = val('cfop_origem')
        cfop_legado = val('cfop')
        if cfop_origem and 'cfop' not in attrs:
            attrs['cfop'] = cfop_origem
        elif cfop_legado and 'cfop_origem' not in attrs:
            attrs['cfop_origem'] = cfop_legado

        ativo = attrs.get('ativo') if 'ativo' in attrs else (inst.ativo if inst else True)
        if ativo:
            cfop_val = cfop_origem or cfop_legado
            if not cfop_val:
                raise serializers.ValidationError({'cfop_entrada': 'Informe o CFOP.'})
            tipo_op = val('tipo_operacao_fiscal')
            nome = val('nome')
            desc = val('descricao_cenario')
            if not tipo_op and not nome and not desc:
                raise serializers.ValidationError({'tipo_operacao_fiscal': 'Informe a natureza da operação.'})
            cst = val('cst_icms_esperado')
            csosn = val('csosn_esperado')
            if not (cst or csosn):
                raise serializers.ValidationError({'cst_icms_esperado': 'Informe o CST/CSOSN.'})

        escopo = attrs.get('escopo') or (inst.escopo if inst else None)
        if escopo:
            return attrs

        tem = any(
            [
                cfop_origem or cfop_legado,
                val('ncm'),
                val('uf_origem'),
                val('uf_destino'),
                val('tipo_operacao_fiscal'),
                attrs.get('produto') or (inst.produto_id if inst else None),
                attrs.get('fornecedor') or (inst.fornecedor_id if inst else None),
            ],
        )
        if not tem:
            raise serializers.ValidationError(
                {'detail': 'Informe ao menos um critério de match (CFOP, NCM, UF, produto, fornecedor, etc.).'},
            )
        return attrs

    def create(self, validated_data):
        instance = RegraFiscalEntrada(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class DuplicarRegraFiscalEntradaSerializer(serializers.Serializer):
    uf_origem = serializers.CharField(max_length=2, required=False, allow_blank=True)
    uf_destino = serializers.CharField(max_length=2, required=False, allow_blank=True)
    cfop_origem = serializers.CharField(max_length=8, required=False, allow_blank=True)
    cfop_entrada = serializers.CharField(max_length=8, required=False, allow_blank=True)
    sobrescrever = serializers.BooleanField(default=False, required=False)


class DestinoCopiaConfiguracaoSerializer(serializers.Serializer):
    uf_origem = serializers.CharField(max_length=2, required=False, allow_blank=True)
    uf_destino = serializers.CharField(max_length=2, required=False, allow_blank=True)
    cfop_origem = serializers.CharField(max_length=8, required=False, allow_blank=True)
    cfop_entrada = serializers.CharField(max_length=8, required=False, allow_blank=True)


class CopiarConfiguracaoEscopoSerializer(serializers.Serializer):
    origem_regra_id = serializers.IntegerField()
    destinos = DestinoCopiaConfiguracaoSerializer(many=True)
    sobrescrever = serializers.BooleanField(default=False, required=False)

    def validate_destinos(self, value):
        if not value:
            raise serializers.ValidationError('Informe ao menos um destino.')
        return value


class CenarioFiscalSaidaEscopoSerializer(serializers.ModelSerializer):
    cenario = serializers.PrimaryKeyRelatedField(read_only=True)
    produto_id = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.all(),
        source='produto',
        allow_null=True,
        required=False,
    )
    configuracoes_count = serializers.IntegerField(read_only=True, default=0)
    label = serializers.SerializerMethodField()
    tem_reforma = serializers.SerializerMethodField()
    tem_recomendacoes_nfe = serializers.SerializerMethodField()

    class Meta:
        model = CenarioFiscalSaidaEscopo
        fields = (
            'id',
            'cenario',
            'tipo_escopo',
            'ncm',
            'produto_id',
            'prioridade_escopo',
            'ativo',
            'configuracoes_count',
            'label',
            'tem_reforma',
            'tem_recomendacoes_nfe',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def get_label(self, obj: CenarioFiscalSaidaEscopo) -> str:
        return label_escopo_saida(obj)

    def get_tem_reforma(self, obj: CenarioFiscalSaidaEscopo) -> bool:
        from apps.regras_fiscais.reforma_tributaria_config import reforma_tributaria_preenchida

        return any(
            reforma_tributaria_preenchida(r.reforma_tributaria)
            for r in obj.configuracoes.only('reforma_tributaria')
        )

    def get_tem_recomendacoes_nfe(self, obj: CenarioFiscalSaidaEscopo) -> bool:
        return any(
            recomendacoes_nfe_preenchidas(r.recomendacoes_nfe)
            for r in obj.configuracoes.only('recomendacoes_nfe')
        )

    def validate(self, attrs):
        inst = self.instance
        tipo = attrs.get('tipo_escopo') or (inst.tipo_escopo if inst else '')
        produto = attrs.get('produto') if 'produto' in attrs else (inst.produto if inst else None)
        ncm = (attrs.get('ncm') if 'ncm' in attrs else (inst.ncm if inst else '')) or ''
        ncm = ncm.strip()

        if tipo == CenarioFiscalSaidaEscopo.TipoEscopo.PRODUTO and not produto:
            raise serializers.ValidationError({'produto_id': 'Informe o produto para escopo PRODUTO.'})
        if tipo in (
            CenarioFiscalSaidaEscopo.TipoEscopo.NCM,
            CenarioFiscalSaidaEscopo.TipoEscopo.NCM_PREFIXO,
        ) and not ncm:
            raise serializers.ValidationError({'ncm': 'Informe o NCM para este escopo.'})
        if tipo == CenarioFiscalSaidaEscopo.TipoEscopo.GERAL:
            attrs['ncm'] = ''
            attrs['produto'] = None
        return attrs


class CenarioFiscalSaidaSerializer(serializers.ModelSerializer):
    empresa_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source='empresa',
        allow_null=True,
        required=False,
    )
    total_escopos = serializers.IntegerField(read_only=True)
    total_configuracoes = serializers.IntegerField(read_only=True)

    class Meta:
        model = CenarioFiscalSaida
        fields = (
            'id',
            'nome',
            'empresa_id',
            'regime_tributario',
            'ativo',
            'padrao',
            'observacoes',
            'total_escopos',
            'total_configuracoes',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em', 'total_escopos', 'total_configuracoes')


class CenarioFiscalSaidaDetailSerializer(CenarioFiscalSaidaSerializer):
    escopos = serializers.SerializerMethodField()

    class Meta(CenarioFiscalSaidaSerializer.Meta):
        fields = CenarioFiscalSaidaSerializer.Meta.fields + ('escopos',)

    def get_escopos(self, obj: CenarioFiscalSaida):
        qs = (
            obj.escopos.annotate(configuracoes_count=Count('configuracoes'))
            .order_by('tipo_escopo', 'ncm', 'produto_id', 'id')
        )
        return CenarioFiscalSaidaEscopoSerializer(qs, many=True).data


class RegraFiscalSaidaSerializer(serializers.ModelSerializer):
    cenario_id = serializers.PrimaryKeyRelatedField(
        queryset=CenarioFiscalSaida.objects.all(),
        source='cenario',
        allow_null=True,
        required=False,
    )
    escopo_id = serializers.PrimaryKeyRelatedField(
        queryset=CenarioFiscalSaidaEscopo.objects.all(),
        source='escopo',
        allow_null=True,
        required=False,
    )
    label_configuracao = serializers.SerializerMethodField()
    status_configuracao = serializers.SerializerMethodField()
    resumo_impostos = serializers.SerializerMethodField()

    class Meta:
        model = RegraFiscalSaida
        fields = (
            'id',
            'cenario_id',
            'escopo_id',
            'nome',
            'codigo',
            'ativo',
            'prioridade',
            'uf_origem',
            'uf_destino',
            'destinatario_contribuinte',
            'consumidor_final',
            'cfop_venda',
            'cfop_venda_st',
            'tipo_operacao',
            'descricao_cenario',
            'label_configuracao',
            'status_configuracao',
            'resumo_impostos',
            'cst_icms',
            'csosn',
            'modalidade_bc_icms',
            'aliquota_icms',
            'reducao_bc_icms',
            'motivo_desoneracao_icms',
            'codigo_beneficio_icms',
            'icms_st_aplicavel',
            'cst_icms_st',
            'aliquota_icms_st',
            'mva_st',
            'reducao_bc_st',
            'fcp_aplicavel',
            'aliquota_fcp',
            'aliquota_fcp_st',
            'reducao_bc_fcp',
            'valor_fcp_unidade',
            'reforma_tributaria',
            'cst_ipi',
            'tipo_calculo_ipi',
            'aliquota_ipi',
            'valor_ipi_unidade',
            'enquadramento_ipi',
            'cst_pis',
            'tipo_calculo_pis',
            'aliquota_pis',
            'reducao_base_pis',
            'valor_minimo_pis_unidade',
            'aliquota_pis_st',
            'deduzir_icms_base_pis',
            'cst_cofins',
            'tipo_calculo_cofins',
            'aliquota_cofins',
            'reducao_base_cofins',
            'valor_minimo_cofins_unidade',
            'aliquota_cofins_st',
            'deduzir_icms_base_cofins',
            'movimenta_estoque',
            'gera_financeiro',
            'informacoes_complementares',
            'observacoes',
            'recomendacoes_nfe',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('criado_em', 'atualizado_em')

    def get_label_configuracao(self, obj: RegraFiscalSaida) -> str:
        return gerar_label_regra_fiscal_saida(obj)

    def get_status_configuracao(self, obj: RegraFiscalSaida) -> str:
        from .cenario_fiscal_saida import status_configuracao_saida

        return status_configuracao_saida(obj)

    def get_resumo_impostos(self, obj: RegraFiscalSaida) -> dict[str, str]:
        from .cenario_fiscal_saida import resumo_impostos_saida

        return resumo_impostos_saida(obj)

    def validate_reforma_tributaria(self, value):
        if value in (None, '', {}):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError('reforma_tributaria deve ser um objeto JSON.')
        return normalizar_reforma_tributaria(value)

    def validate_recomendacoes_nfe(self, value):
        if value in (None, '', {}):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError('recomendacoes_nfe deve ser um objeto JSON.')
        return normalizar_recomendacoes_nfe(value)

    def validate_codigo_beneficio_icms(self, value):
        return normalizar_codigo_beneficio_icms(value)

    def validate(self, attrs):
        inst = self.instance
        escopo = attrs.get('escopo') or (inst.escopo if inst else None)
        if escopo and attrs.get('cenario') is None and (inst is None or inst.cenario_id is None):
            attrs['cenario'] = escopo.cenario

        cfop = (attrs.get('cfop_venda') if 'cfop_venda' in attrs else (inst.cfop_venda if inst else '')) or ''
        uf_o = (attrs.get('uf_origem') if 'uf_origem' in attrs else (inst.uf_origem if inst else '')) or ''
        uf_d = (attrs.get('uf_destino') if 'uf_destino' in attrs else (inst.uf_destino if inst else '')) or ''
        if escopo:
            return attrs
        if not any([cfop.strip(), uf_o.strip(), uf_d.strip()]):
            raise serializers.ValidationError(
                {'detail': 'Informe escopo_id ou ao menos CFOP de venda / UF origem / UF destino.'},
            )
        return attrs

    def create(self, validated_data):
        instance = RegraFiscalSaida(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
