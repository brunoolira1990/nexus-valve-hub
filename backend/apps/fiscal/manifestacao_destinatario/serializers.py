"""Serializers — Manifestação do Destinatário."""

from __future__ import annotations

from rest_framework import serializers

from apps.fiscal.manifestacao_destinatario.constants import DESCRICAO_EVENTO_USUARIO, EVENTOS_MANIFESTACAO
from apps.fiscal.models import NFeDestinadaManifestacao, NFeDestinadaManifestacaoEvento


class NFeDestinadaManifestacaoEventoSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField()

    class Meta:
        model = NFeDestinadaManifestacaoEvento
        fields = [
            'id',
            'tipo_acao',
            'codigo_evento',
            'descricao',
            'usuario_nome',
            'ambiente',
            'resultado_resumido',
            'cstat',
            'xmotivo',
            'criado_em',
            'dados_json',
        ]

    def get_usuario_nome(self, obj) -> str:
        if obj.usuario_id and obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return ''


class NFeDestinadaManifestacaoListSerializer(serializers.ModelSerializer):
    chave_resumida = serializers.SerializerMethodField()
    status_manifestacao_label = serializers.CharField(source='get_status_manifestacao_display', read_only=True)
    status_xml_label = serializers.CharField(source='get_status_xml_display', read_only=True)
    ambiente_label = serializers.CharField(source='get_ambiente_display', read_only=True)
    empresa_nome = serializers.CharField(source='empresa.razao_social', read_only=True)

    class Meta:
        model = NFeDestinadaManifestacao
        fields = [
            'id',
            'empresa_id',
            'empresa_nome',
            'chave_acesso',
            'chave_resumida',
            'nsu',
            'cnpj_destinatario',
            'cnpj_emitente',
            'razao_social_emitente',
            'dh_emissao',
            'valor_nf',
            'status_manifestacao',
            'status_manifestacao_label',
            'status_xml',
            'status_xml_label',
            'ambiente',
            'ambiente_label',
            'classificacao_dfe',
            'ultimo_cstat',
            'ultimo_xmotivo',
            'nf_entrada_historica_id',
            'manifestado_em',
            'xml_baixado_em',
            'consultado_em',
        ]

    def get_chave_resumida(self, obj) -> str:
        ch = obj.chave_acesso or ''
        if len(ch) < 12:
            return ch
        return f'{ch[:4]}…{ch[-8:]}'


class NFeDestinadaManifestacaoDetailSerializer(NFeDestinadaManifestacaoListSerializer):
    eventos = NFeDestinadaManifestacaoEventoSerializer(many=True, read_only=True)
    resumo_json = serializers.JSONField(read_only=True)

    class Meta(NFeDestinadaManifestacaoListSerializer.Meta):
        fields = NFeDestinadaManifestacaoListSerializer.Meta.fields + [
            'ie_emitente',
            'resumo_json',
            'criado_em',
            'eventos',
        ]


class ConsultaManifestacaoSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    limite_lotes = serializers.IntegerField(required=False, default=3, min_value=1, max_value=20)


class ManifestarDestinatarioSerializer(serializers.Serializer):
    evento = serializers.ChoiceField(choices=sorted(EVENTOS_MANIFESTACAO))
    justificativa = serializers.CharField(required=False, allow_blank=True, default='')
    confirmacao_explicita = serializers.BooleanField()

    def validate(self, attrs):
        evento = attrs.get('evento')
        attrs['descricao_evento'] = DESCRICAO_EVENTO_USUARIO.get(evento, '')
        return attrs


class BaixarXmlDestinatarioSerializer(serializers.Serializer):
    confirmacao_explicita = serializers.BooleanField()


class IniciarPorChaveSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    chave_acesso = serializers.CharField(max_length=44)
    nf_entrada_historica_id = serializers.IntegerField(required=False, allow_null=True)
