"""Serializers API — integração SEFAZ NF-e 3.6."""

from rest_framework import serializers

from apps.fiscal.models import NFeSefazStatusConsulta


class NFeSefazStatusConsultaSerializer(serializers.ModelSerializer):
    empresa_razao_social = serializers.CharField(source='empresa.razao_social', read_only=True)
    empresa_cnpj = serializers.CharField(source='empresa.cnpj', read_only=True)
    consultado_por_nome = serializers.SerializerMethodField()

    class Meta:
        model = NFeSefazStatusConsulta
        fields = (
            'id',
            'empresa',
            'empresa_razao_social',
            'empresa_cnpj',
            'uf',
            'ambiente',
            'modelo',
            'sucesso',
            'c_stat',
            'x_motivo',
            'ver_aplic',
            'tp_amb',
            'c_uf',
            'dh_recbto',
            't_med',
            'versao_retorno',
            'servico_operacional',
            'certificado_valido',
            'certificado_cnpj',
            'certificado_validade_fim',
            'erro_tecnico',
            'tipo_erro',
            'raw_response',
            'traceback_resumido',
            'mensagens',
            'consultado_em',
            'consultado_por',
            'consultado_por_nome',
        )
        read_only_fields = fields

    def get_consultado_por_nome(self, obj) -> str | None:
        user = obj.consultado_por
        if not user:
            return None
        return user.get_full_name() or user.get_username()


class ConsultarStatusServicoInputSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    uf = serializers.CharField(max_length=2, required=False, allow_blank=True)
    homologacao = serializers.BooleanField(default=True)
