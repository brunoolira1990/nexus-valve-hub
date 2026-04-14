from rest_framework import serializers

from .models import Lancamento, PlanoConta


class PlanoContaSerializer(serializers.ModelSerializer):
    pai_id = serializers.PrimaryKeyRelatedField(
        queryset=PlanoConta.objects.all(),
        source='pai',
        allow_null=True,
        required=False,
    )
    filhos = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PlanoConta
        exclude = ('pai',)

    def get_filhos(self, obj):
        return [
            {
                'id': ch.id,
                'codigo': ch.codigo,
                'nome': ch.nome,
                'tipo': ch.tipo,
                'pai_id': ch.pai_id,
            }
            for ch in obj.filhos.all()
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['pai_id'] = instance.pai_id
        return data


class LancamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lancamento
        fields = '__all__'
