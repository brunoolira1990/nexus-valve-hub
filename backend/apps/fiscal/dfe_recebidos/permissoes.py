"""Permissões para captura manual DF-e recebidos via SEFAZ."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

GRUPOS_CAPTURA_DFE_RECEBIDOS = frozenset({'admin', 'administrador', 'fiscal'})

MSG_SEM_PERMISSAO_CAPTURA = (
    'Seu perfil não possui permissão para capturar DF-e da SEFAZ. '
    'Contate um administrador do módulo fiscal.'
)


def usuario_pode_capturar_dfe_recebidos(usuario: AbstractBaseUser | None) -> bool:
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    if getattr(usuario, 'is_superuser', False):
        return True
    grupos = set(usuario.groups.values_list('name', flat=True))
    return bool(grupos & GRUPOS_CAPTURA_DFE_RECEBIDOS)
