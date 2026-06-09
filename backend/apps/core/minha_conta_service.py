"""Atualização de dados pessoais — Minha conta ERP 4.0.14.9.4."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.cadastros.colaborador_senha import email_operacional_valido, validar_email_operacional
from apps.cadastros.models import Colaborador

User = get_user_model()


@transaction.atomic
def atualizar_minha_conta(user: User, *, email: str | None = None, telefone: str | None = None) -> User:
    colaborador = (
        Colaborador.objects.filter(usuario=user).order_by('-ativo', 'pk').first()
    )

    if email is not None:
        email_norm = validar_email_operacional(email)
        if User.objects.filter(email__iexact=email_norm).exclude(pk=user.pk).exists():
            raise ValueError('Já existe um usuário com este e-mail.')
        user.email = email_norm
        user.save(update_fields=['email'])
        if colaborador and not (colaborador.email or '').strip():
            colaborador.email = email_norm
            colaborador.save(update_fields=['email', 'atualizado_em'])

    if telefone is not None and colaborador:
        colaborador.telefone = (telefone or '').strip()[:32]
        colaborador.save(update_fields=['telefone', 'atualizado_em'])

    return user
