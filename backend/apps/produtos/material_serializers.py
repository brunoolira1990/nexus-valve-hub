"""Serializers para o model Material."""

from __future__ import annotations

from rest_framework import serializers

from apps.produtos.material_models import Material


class MaterialSerializer(serializers.ModelSerializer):
    """Serializer completo de Material com contagem de produtos vinculados."""

    # Contagem de produtos que referenciam este material (campo futuro).
    # Por ora retorna 0 — será preenchido quando Produto.material_ref existir.
    produtos_count = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = [
            'id',
            'codigo',
            'nome',
            'nome_curto',
            'categoria',
            'norma_astm',
            'ncm_sugerido',
            'densidade_kg_m3',
            'aliases',
            'ativo',
            'ordem',
            'criado_em',
            'atualizado_em',
            'produtos_count',
        ]
        read_only_fields = ['id', 'codigo', 'criado_em', 'atualizado_em', 'produtos_count']

    def get_produtos_count(self, obj: Material) -> int:
        """Retorna o número de produtos vinculados a este material.

        Quando Produto.material_ref (ForeignKey) for criado, trocar por:
            return obj.produtos.count()
        """
        return 0
