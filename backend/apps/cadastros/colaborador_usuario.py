"""Validação de vínculo único Colaborador ↔ User (Comercial 2.4.2)."""

from __future__ import annotations

from rest_framework import serializers

from apps.cadastros.models import Colaborador


def validar_usuario_colaborador_unico(usuario, *, instance: Colaborador | None = None) -> None:
    """Impede o mesmo login em mais de um colaborador ativo."""
    if usuario is None:
        return
    qs = Colaborador.objects.filter(usuario=usuario, ativo=True)
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    outro = qs.order_by('pk').first()
    if outro:
        nome = (outro.nome or outro.codigo or str(outro.pk)).strip()
        raise serializers.ValidationError(
            {'usuario_id': f'Este usuário já está vinculado ao colaborador {nome}.'},
        )
