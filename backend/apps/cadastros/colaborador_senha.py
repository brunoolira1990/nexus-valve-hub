"""Senha e e-mail — ERP 4.0.14.9.2."""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from apps.cadastros.models import Colaborador

User = get_user_model()

GRUPOS_ADMIN = ('admin', 'administrador')


def usuario_eh_admin(user: User | None) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=GRUPOS_ADMIN).exists()


def email_operacional_valido(email: str) -> bool:
    valor = (email or '').strip()
    if not valor or '@' not in valor:
        return False
    local, _, domain = valor.partition('@')
    if not local or not domain or '.' not in domain:
        return False
    try:
        validate_email(valor)
    except DjangoValidationError:
        return False
    return True


def validar_email_operacional(email: str) -> str:
    valor = (email or '').strip()
    if not email_operacional_valido(valor):
        raise ValueError('Informe um e-mail válido.')
    return valor


def validar_par_senhas(senha: str, confirmar: str, *, campo_confirmar: str = 'confirmar_senha') -> str:
    s = (senha or '').strip()
    c = (confirmar or '').strip()
    if not s:
        raise ValueError('Informe a senha.')
    if not c:
        raise ValueError('Confirme a senha.')
    if s != c:
        raise ValueError('As senhas informadas não conferem.')
    return s


def validar_nova_senha(user: User, senha: str) -> str:
    s = (senha or '').strip()
    if not s:
        raise ValueError('Informe a nova senha.')
    try:
        validate_password(s, user=user)
    except DjangoValidationError as exc:
        raise ValueError('; '.join(exc.messages)) from exc
    return s


def aplicar_senha(user: User, senha: str) -> None:
    user.set_password(validar_nova_senha(user, senha))
    user.save(update_fields=['password'])


def alterar_senha_proprio_usuario(user: User, *, senha_atual: str, nova_senha: str, confirmar_senha: str) -> None:
    atual = (senha_atual or '').strip()
    if not atual:
        raise ValueError('Informe a senha atual.')
    if not user.check_password(atual):
        raise ValueError('Senha atual incorreta.')
    validar_par_senhas(nova_senha, confirmar_senha, campo_confirmar='confirmar_senha')
    aplicar_senha(user, nova_senha)


def redefinir_senha_colaborador(colaborador: Colaborador, *, nova_senha: str, confirmar_senha: str) -> User:
    if not colaborador.usuario_id or not colaborador.usuario:
        raise ValueError('Colaborador não possui usuário vinculado.')
    user = colaborador.usuario
    validar_par_senhas(nova_senha, confirmar_senha)
    aplicar_senha(user, nova_senha)
    return user
