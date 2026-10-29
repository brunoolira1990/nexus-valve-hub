from rest_framework import serializers

from .models import NotaChatter


class NotaChatterSerializer(serializers.ModelSerializer):
    autor_nome = serializers.SerializerMethodField()

    class Meta:
        model = NotaChatter
        # entity_type/entity_id são escritos pelo cliente (a nota nasce presa a uma
        # entidade); autor, autor_nome e as datas nascem do request — nunca do payload.
        fields = ('id', 'entity_type', 'entity_id', 'texto', 'autor', 'autor_nome', 'criado_em', 'atualizado_em')
        read_only_fields = ('id', 'autor', 'autor_nome', 'criado_em', 'atualizado_em')

    def validate_entity_type(self, valor: str) -> str:
        # Normalizada: 'Familia ' e 'familia' não podem virar duas timelines distintas.
        return (valor or '').strip().lower()

    def validate_texto(self, valor: str) -> str:
        texto = (valor or '').strip()
        if not texto:
            raise serializers.ValidationError('A nota não pode ficar vazia.')
        return texto

    def get_autor_nome(self, obj: NotaChatter) -> str | None:
        user = obj.autor
        if user is None:
            return None
        return (user.get_full_name() or '').strip() or user.get_username()
