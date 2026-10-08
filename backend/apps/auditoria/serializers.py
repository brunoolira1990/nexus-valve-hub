from rest_framework import serializers

from apps.auditoria.models import RegistroAuditoria


class AtorAuditoriaSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    nome = serializers.CharField(allow_null=True)


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    ator = serializers.SerializerMethodField()

    class Meta:
        model = RegistroAuditoria
        fields = ('id', 'operacao', 'ator', 'criado_em', 'alteracoes')
        read_only_fields = fields

    def get_ator(self, obj: RegistroAuditoria) -> dict:
        user = obj.ator
        if user is None:
            return {'id': None, 'nome': None}
        nome = (user.get_full_name() or '').strip() or user.get_username()
        return {'id': user.pk, 'nome': nome}
