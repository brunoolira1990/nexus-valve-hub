"""Grupos/permissões estáveis para suítes NF-e 4015 (evita deadlock em --keepdb)."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, Group
from django.db import IntegrityError

GRUPOS_4015 = ('admin', 'administrador', 'fiscal', 'fiscal_nfe_producao')

_cache: dict[str, Group] = {}


def obter_ou_criar_grupo_teste(name: str) -> Group:
    """Retorna grupo por nome; cria uma vez de forma idempotente (sem get_or_create concorrente)."""
    if name in _cache:
        cached = Group.objects.filter(pk=_cache[name].pk).first()
        if cached:
            return cached

    existente = Group.objects.filter(name=name).order_by('pk').first()
    if existente:
        _cache[name] = existente
        return existente

    try:
        criado = Group.objects.create(name=name)
    except IntegrityError:
        criado = Group.objects.get(name=name)

    _cache[name] = criado
    return criado


def garantir_grupos_4015() -> dict[str, Group]:
    return {nome: obter_ou_criar_grupo_teste(nome) for nome in GRUPOS_4015}


def vincular_grupo_teste(user: AbstractBaseUser, group_name: str) -> None:
    user.groups.add(obter_ou_criar_grupo_teste(group_name))


class NFe4015GruposMixin:
    """Pré-cria grupos uma vez por classe de teste (reduz contenção no auth_group)."""

    grupos_4015: dict[str, Group]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.grupos_4015 = garantir_grupos_4015()
