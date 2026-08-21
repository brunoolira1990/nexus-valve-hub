from rest_framework import serializers

from .models import Notificacao


class NotificacaoSerializer(serializers.ModelSerializer):
    modulo_label = serializers.CharField(source='get_modulo_display', read_only=True)
    tipo_label = serializers.CharField(source='get_tipo_display', read_only=True)
    prioridade_label = serializers.CharField(source='get_prioridade_display', read_only=True)

    class Meta:
        model = Notificacao
        fields = (
            'id',
            'modulo',
            'modulo_label',
            'tipo',
            'tipo_label',
            'prioridade',
            'prioridade_label',
            'titulo',
            'mensagem',
            'url_destino',
            'objeto_tipo',
            'objeto_id',
            'lida',
            'arquivada',
            'criado_em',
            'lida_em',
            'arquivada_em',
        )
        read_only_fields = fields
