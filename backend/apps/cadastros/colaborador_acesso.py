"""Acesso ao sistema via colaborador — ERP 4.0.14.9.1/4.0.14.9.2/4.0.14.10.2."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.cadastros.colaborador_senha import (
    email_operacional_valido,
    usuario_eh_admin,
    validar_email_operacional,
    validar_par_senhas,
    validar_nova_senha,
)
from apps.cadastros.colaborador_usuario import validar_usuario_colaborador_unico
from apps.cadastros.models import Colaborador
from apps.core.usuario_exibicao import email_eh_tecnico_local

User = get_user_model()

GRUPOS_PERFIL: dict[str, str] = {
    'admin': 'admin',
    'administrador': 'admin',
    'financeiro': 'financeiro',
    'fiscal': 'fiscal',
    'compras': 'compras',
    'comercial': 'comercial',
    'estoque': 'estoque',
    'produtos': 'produtos',
    'consulta': 'consulta',
    'operador': 'operador',
}

PERFIL_LABELS: dict[str, str] = {
    'admin': 'Administrador',
    'administrador': 'Administrador',
    'financeiro': 'Financeiro',
    'fiscal': 'Fiscal',
    'compras': 'Compras',
    'comercial': 'Comercial',
    'estoque': 'Estoque',
    'produtos': 'Produtos',
    'consulta': 'Consulta',
    'operador': 'Operador',
    'superusuario': 'Superusuário',
}

PERFIS_DISPONIVEIS = (
    'administrador',
    'financeiro',
    'fiscal',
    'compras',
    'comercial',
    'estoque',
    'produtos',
    'consulta',
)


class AcessoStatus:
    SEM_USUARIO = 'SEM_USUARIO'
    USUARIO_ATIVO = 'USUARIO_ATIVO'
    USUARIO_INATIVO = 'USUARIO_INATIVO'
    SEM_PERFIL = 'SEM_PERFIL'
    SUPERUSUARIO = 'SUPERUSUARIO'


ACESSO_STATUS_LABELS = {
    AcessoStatus.SEM_USUARIO: 'Sem acesso',
    AcessoStatus.USUARIO_ATIVO: 'Usuário ativo',
    AcessoStatus.USUARIO_INATIVO: 'Acesso inativo',
    AcessoStatus.SEM_PERFIL: 'Sem perfil',
    AcessoStatus.SUPERUSUARIO: 'Superusuário',
}


def _slug_username(base: str) -> str:
    s = unicodedata.normalize('NFKD', base).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-zA-Z0-9._-]+', '.', s.lower()).strip('.')
    return (s[:120] or 'usuario').strip('.')


def _gerar_username_unico(email: str, nome: str, codigo: str) -> str:
    local = (email.split('@')[0] if '@' in email else '').strip()
    candidatos = [local, _slug_username(nome), _slug_username(codigo), 'usuario']
    for base in candidatos:
        if not base:
            continue
        username = _slug_username(base)[:150]
        if not User.objects.filter(username=username).exists():
            return username
        for i in range(2, 100):
            cand = f'{username[:140]}{i}'
            if not User.objects.filter(username=cand).exists():
                return cand
    raise ValueError('Não foi possível gerar um nome de usuário único.')


def _grupo_nome_perfil(perfil: str) -> str:
    return GRUPOS_PERFIL.get((perfil or '').strip().lower(), 'consulta')


def _aplicar_grupo(user: User, perfil: str) -> Group | None:
    if user.is_superuser:
        return None
    grupo_nome = _grupo_nome_perfil(perfil)
    grupo, _ = Group.objects.get_or_create(name=grupo_nome)
    user.groups.set([grupo])
    return grupo


def _grupos_usuario(user: User) -> list[str]:
    if user.is_superuser:
        return ['superusuario']
    return list(user.groups.order_by('name').values_list('name', flat=True))


def _perfil_label(user: User) -> str:
    if user.is_superuser:
        return PERFIL_LABELS['superusuario']
    grupos = _grupos_usuario(user)
    if not grupos:
        return ''
    g = grupos[0]
    return PERFIL_LABELS.get(g, g.replace('_', ' ').title())


def _resolver_status(user: User | None) -> str:
    if not user:
        return AcessoStatus.SEM_USUARIO
    if user.is_superuser:
        return AcessoStatus.SUPERUSUARIO
    if not user.is_active:
        return AcessoStatus.USUARIO_INATIVO
    if not user.groups.exists():
        return AcessoStatus.SEM_PERFIL
    return AcessoStatus.USUARIO_ATIVO


def _email_tecnico_usuario(user: User | None) -> bool:
    if not user:
        return False
    email = (user.email or '').strip()
    if not email:
        return True
    return email_eh_tecnico_local(email) or not email_operacional_valido(email)


def _contar_superusers_ativos(*, excluir_pk: int | None = None) -> int:
    qs = User.objects.filter(is_active=True, is_superuser=True)
    if excluir_pk:
        qs = qs.exclude(pk=excluir_pk)
    return qs.count()


def _validar_email_usuario_ativo(email: str, user: User, ativo: bool) -> str:
    email_norm = (email or '').strip()
    if not ativo:
        return email_norm
    if not email_norm:
        raise ValueError('Informe um e-mail válido para produção.')
    validar_email_operacional(email_norm)
    if email_eh_tecnico_local(email_norm):
        raise ValueError('Informe um e-mail válido para produção.')
    if User.objects.filter(is_active=True, email__iexact=email_norm).exclude(pk=user.pk).exists():
        raise ValueError('Já existe outro usuário ativo com este e-mail.')
    return email_norm


def _validar_usuario_ativo_completo(user: User) -> None:
    if not user.is_active:
        return
    if user.is_superuser:
        if _email_tecnico_usuario(user):
            raise ValueError('Informe um e-mail válido para produção.')
        return
    if not user.groups.exists():
        raise ValueError('Usuário ativo precisa ter um perfil de acesso ou ser superusuário.')
    if _email_tecnico_usuario(user):
        raise ValueError('Informe um e-mail válido para produção.')


def badge_acesso_listagem(colaborador: Colaborador) -> str:
    user = colaborador.usuario if colaborador.usuario_id else None
    status = _resolver_status(user)
    if status == AcessoStatus.SEM_USUARIO:
        return 'Sem acesso'
    if status == AcessoStatus.USUARIO_INATIVO:
        return 'Acesso inativo'
    if status == AcessoStatus.SUPERUSUARIO:
        return 'Superusuário'
    if status == AcessoStatus.SEM_PERFIL:
        return 'Sem perfil'
    if status == AcessoStatus.USUARIO_ATIVO:
        return _perfil_label(user) or 'Usuário ativo'
    return ACESSO_STATUS_LABELS.get(status, status)


def sugerir_perfil_colaborador(colaborador: Colaborador) -> str | None:
    if colaborador.eh_administrador:
        return 'administrador'
    if colaborador.eh_responsavel_financeiro:
        return 'financeiro'
    if colaborador.eh_responsavel_fiscal:
        return 'fiscal'
    if colaborador.eh_comprador:
        return 'compras'
    if colaborador.eh_vendedor:
        return 'comercial'
    if colaborador.eh_responsavel_estoque:
        return 'estoque'
    return None


def gerar_link_redefinicao_senha(user: User) -> dict[str, str]:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return {'uid': uid, 'token': token}


def montar_acesso_colaborador(colaborador: Colaborador, *, actor: User | None = None) -> dict[str, Any]:
    user = colaborador.usuario if colaborador.usuario_id else None
    status = _resolver_status(user)
    grupos = _grupos_usuario(user) if user else []
    perfil_label = _perfil_label(user) if user else ''
    email_tecnico = _email_tecnico_usuario(user) if user and user.is_active else False
    sem_perfil = bool(user and user.is_active and not user.is_superuser and not user.groups.exists())
    admin_actor = usuario_eh_admin(actor)

    pode_criar = admin_actor and not colaborador.usuario_id and colaborador.ativo
    pode_vincular = admin_actor and not colaborador.usuario_id
    pode_editar = admin_actor and bool(user)
    pode_desativar = False
    if admin_actor and user and user.is_active:
        if actor and actor.pk == user.pk:
            pode_desativar = False
        elif user.is_superuser and _contar_superusers_ativos(excluir_pk=user.pk) == 0:
            pode_desativar = False
        else:
            pode_desativar = True
    pode_reenviar = False  # 4.0.14.9.2 — sem convite por e-mail
    pode_redefinir_senha = bool(admin_actor and user and user.is_active)
    pode_definir_perfil = bool(
        admin_actor and user and user.is_active and not user.is_superuser and status == AcessoStatus.SEM_PERFIL,
    )

    motivo_bloqueio = ''
    if not colaborador.ativo and user and user.is_active:
        motivo_bloqueio = 'Colaborador inativo com usuário ativo — revise o vínculo.'
    elif status == AcessoStatus.SEM_PERFIL:
        motivo_bloqueio = 'Usuário ativo sem perfil/grupo. Use Editar acesso para definir um perfil.'
    elif email_tecnico:
        motivo_bloqueio = 'Este e-mail é técnico/local. Para produção, informe um e-mail real em Editar acesso.'

    sugestao = sugerir_perfil_colaborador(colaborador)
    badge = badge_acesso_listagem(colaborador)

    acesso_sistema = {
        'tem_usuario': bool(user),
        'usuario_id': user.pk if user else None,
        'login': user.username if user else '',
        'email': (user.email or '') if user else '',
        'ativo': bool(user and user.is_active),
        'is_staff': bool(user and user.is_staff),
        'is_superuser': bool(user and user.is_superuser),
        'perfil_principal': perfil_label or ('Sem perfil' if sem_perfil else ''),
        'grupos': [] if user and user.is_superuser else grupos,
        'sem_perfil': sem_perfil,
        'email_tecnico': email_tecnico,
        'pode_editar_acesso': pode_editar,
        'pode_redefinir_senha': pode_redefinir_senha,
        'pode_desativar': pode_desativar,
    }

    return {
        'acesso_status': status,
        'acesso_status_label': ACESSO_STATUS_LABELS.get(status, status),
        'badge_acesso': badge,
        'status_acesso': status.lower(),  # legado 4.0.14.8
        'usuario_ativo': bool(user and user.is_active),
        'usuario_is_staff': bool(user and user.is_staff),
        'usuario_is_superuser': bool(user and user.is_superuser),
        'usuario_grupos': grupos,
        'perfil_acesso': grupos[0] if grupos and grupos[0] != 'superusuario' else '',
        'perfil_acesso_label': perfil_label,
        'perfil_sugerido': sugestao,
        'perfil_sugerido_label': PERFIL_LABELS.get(_grupo_nome_perfil(sugestao), '') if sugestao else '',
        'sem_perfil': sem_perfil,
        'email_tecnico': email_tecnico,
        'pode_criar_usuario': pode_criar,
        'pode_vincular_usuario': pode_vincular,
        'pode_editar_acesso': pode_editar,
        'pode_desativar_acesso': pode_desativar,
        'pode_reenviar_convite': pode_reenviar,
        'pode_redefinir_senha': pode_redefinir_senha,
        'pode_definir_perfil': pode_definir_perfil,
        'motivo_bloqueio_acesso': motivo_bloqueio,
        'acesso_sistema': acesso_sistema,
    }


@transaction.atomic
def editar_acesso_colaborador(
    colaborador: Colaborador,
    *,
    actor: User,
    ativo: bool | None = None,
    email: str | None = None,
    perfil: str | None = None,
    is_staff: bool | None = None,
    is_superuser: bool | None = None,
) -> User:
    if not usuario_eh_admin(actor):
        raise ValueError('Apenas administradores podem editar acesso de usuários.')
    if not colaborador.usuario_id or not colaborador.usuario:
        raise ValueError('Colaborador não possui usuário vinculado.')

    user = colaborador.usuario

    if ativo is False and actor.pk == user.pk:
        raise ValueError('Não é permitido desativar o próprio acesso.')

    if is_superuser is False and user.is_superuser and user.is_active:
        if _contar_superusers_ativos(excluir_pk=user.pk) == 0:
            raise ValueError('Não é permitido remover o último administrador/superusuário ativo.')
        if actor.pk == user.pk:
            raise ValueError('Não é permitido remover o próprio superusuário se isso deixar o sistema sem administrador.')

    if ativo is False and user.is_superuser and user.is_active and _contar_superusers_ativos(excluir_pk=user.pk) == 0:
        raise ValueError('Não é permitido remover o último administrador/superusuário ativo.')

    if email is not None:
        ativo_eff = ativo if ativo is not None else user.is_active
        user.email = _validar_email_usuario_ativo(email, user, ativo_eff)

    if is_staff is not None:
        user.is_staff = bool(is_staff)

    if is_superuser is not None:
        if is_superuser and not actor.is_superuser:
            raise ValueError('Apenas superusuário pode conceder status de superusuário.')
        user.is_superuser = bool(is_superuser)

    if ativo is not None:
        user.is_active = bool(ativo)

    if perfil is not None:
        perfil_norm = (perfil or '').strip().lower()
        if user.is_superuser:
            pass
        elif perfil_norm:
            if perfil_norm not in PERFIS_DISPONIVEIS:
                raise ValueError('Perfil de acesso inválido.')
            _aplicar_grupo(user, perfil_norm)
        else:
            user.groups.clear()

    _validar_usuario_ativo_completo(user)
    user.save()
    return user


@transaction.atomic
def definir_perfil_acesso_colaborador(colaborador: Colaborador, *, perfil: str) -> User:
    if not colaborador.usuario_id or not colaborador.usuario:
        raise ValueError('Colaborador não possui usuário vinculado.')
    if colaborador.usuario.is_superuser:
        raise ValueError('Superusuário não pode ter perfil alterado por esta tela.')
    perfil = (perfil or '').strip()
    if not perfil:
        raise ValueError('Selecione um perfil de acesso.')
    _aplicar_grupo(colaborador.usuario, perfil)
    return colaborador.usuario


@transaction.atomic
def vincular_usuario_colaborador(
    colaborador: Colaborador,
    user: User,
    *,
    perfil: str | None = None,
) -> Colaborador:
    if colaborador.usuario_id:
        raise ValueError('Colaborador já possui usuário vinculado.')
    validar_usuario_colaborador_unico(user, instance=colaborador)

    if not user.is_superuser:
        if perfil:
            _aplicar_grupo(user, perfil)
        elif not user.groups.exists():
            raise ValueError('Selecione um perfil de acesso para o usuário vinculado.')

    if not colaborador.ativo and user.is_active:
        raise ValueError('Colaborador inativo não pode receber usuário ativo sem revisão.')

    colaborador.usuario = user
    colaborador.save(update_fields=['usuario', 'atualizado_em'])
    return colaborador


@transaction.atomic
def criar_usuario_para_colaborador(
    colaborador: Colaborador,
    *,
    email: str,
    nome: str = '',
    perfil: str = '',
    ativo: bool = True,
    senha: str = '',
    confirmar_senha: str = '',
) -> User:
    if colaborador.usuario_id:
        raise ValueError('Colaborador já possui usuário vinculado.')
    email_norm = validar_email_operacional(email or colaborador.email or '')
    if ativo and email_eh_tecnico_local(email_norm):
        raise ValueError('Informe um e-mail válido para produção.')
    perfil = (perfil or '').strip()
    if not perfil:
        raise ValueError('Selecione um perfil de acesso.')
    if User.objects.filter(email__iexact=email_norm).exists():
        raise ValueError('Já existe um usuário com este e-mail.')

    nome_final = (nome or colaborador.nome or '').strip()
    if not nome_final:
        raise ValueError('Informe o nome do usuário.')

    senha_final = validar_par_senhas(senha, confirmar_senha)

    username = _gerar_username_unico(email_norm, nome_final, colaborador.codigo or '')
    user = User(username=username, email=email_norm, is_active=ativo)
    partes = nome_final.split(None, 1)
    user.first_name = partes[0]
    user.last_name = partes[1] if len(partes) > 1 else ''
    user.set_password(validar_nova_senha(user, senha_final))
    user.save()
    _aplicar_grupo(user, perfil)

    colaborador.usuario = user
    if not (colaborador.email or '').strip():
        colaborador.email = email_norm
    validar_usuario_colaborador_unico(user, instance=colaborador)
    colaborador.save(update_fields=['usuario', 'email', 'atualizado_em'])

    return user


@transaction.atomic
def desativar_acesso_colaborador(
    colaborador: Colaborador,
    *,
    motivo: str = '',
    actor: User | None = None,
) -> Colaborador:
    if not colaborador.usuario_id or not colaborador.usuario:
        raise ValueError('Colaborador não possui usuário vinculado.')
    user = colaborador.usuario
    if actor and actor.pk == user.pk:
        raise ValueError('Não é permitido desativar o próprio acesso.')
    if user.is_superuser and user.is_active and _contar_superusers_ativos(excluir_pk=user.pk) == 0:
        raise ValueError('Não é permitido remover o último administrador/superusuário ativo.')
    user.is_active = False
    user.save(update_fields=['is_active'])
    return colaborador


# Compatibilidade 4.0.14.8
def status_acesso_colaborador(colaborador: Colaborador) -> str:
    return montar_acesso_colaborador(colaborador)['status_acesso']
