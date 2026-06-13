"""Permissões de emissão NF-e Saída produção SEFAZ — restritas (Fase 3C)."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

# Grupo genérico «fiscal» NÃO concede produção — apenas perfis abaixo.
# «fiscal_nfe_producao» = fiscal explicitamente autorizado pela direção/contador.
GRUPOS_EMISSAO_NFE_PRODUCAO = frozenset({'admin', 'administrador', 'fiscal_nfe_producao'})

MSG_SEM_PERMISSAO_USUARIO = (
    'Seu perfil não possui permissão para emitir NF-e em produção SEFAZ. '
    'Contate um administrador.'
)


def usuario_pode_emitir_nfe_producao(usuario: AbstractBaseUser | None) -> bool:
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    if getattr(usuario, 'is_superuser', False):
        return True
    grupos = set(usuario.groups.values_list('name', flat=True))
    return bool(grupos & GRUPOS_EMISSAO_NFE_PRODUCAO)


def exigir_permissao_usuario_producao(usuario: AbstractBaseUser | None) -> None:
    if not usuario_pode_emitir_nfe_producao(usuario):
        from apps.fiscal.nfe_emissao.config_producao import NFeProducaoDesabilitadaError

        raise NFeProducaoDesabilitadaError(MSG_SEM_PERMISSAO_USUARIO)
