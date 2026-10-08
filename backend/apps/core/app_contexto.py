"""Contexto leve do app — ERP 4.0.14.9.3/4.0.14.9.4."""

from __future__ import annotations

import os
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model

from apps.cadastros.colaborador_acesso import _perfil_label
from apps.cadastros.models import Colaborador, Empresa
from apps.core.usuario_exibicao import email_eh_tecnico_local, nome_curto_usuario, resolver_nome_exibicao_usuario

User = get_user_model()


def resolver_ambiente_app() -> str:
    label = (os.environ.get('NEXUS_APP_AMBIENTE') or '').strip().lower()
    if label in ('homologacao', 'producao'):
        return label
    return 'homologacao' if settings.DEBUG else 'producao'


def _nome_exibicao_empresa_header(empresa: Empresa) -> str:
    """Nome completo para o cabeçalho (razão social preferida)."""
    return (empresa.razao_social or empresa.nome_fantasia or '').strip()


def _nome_curto_empresa(empresa: Empresa) -> str:
    fantasia = (empresa.nome_fantasia or '').strip()
    if fantasia:
        return fantasia
    return (empresa.razao_social or '').strip()


def _funcoes_colaborador(colaborador: Colaborador) -> list[str]:
    funcoes = []
    if colaborador.eh_vendedor:
        funcoes.append('Vendedor')
    if colaborador.eh_comprador:
        funcoes.append('Comprador')
    if colaborador.eh_responsavel_fiscal:
        funcoes.append('Fiscal')
    if colaborador.eh_responsavel_financeiro:
        funcoes.append('Financeiro')
    if colaborador.eh_responsavel_estoque:
        funcoes.append('Estoque')
    if colaborador.eh_responsavel_qualidade:
        funcoes.append('Qualidade')
    if colaborador.eh_administrador:
        funcoes.append('Admin')
    return funcoes


def _colaborador_vinculado(user: User) -> Colaborador | None:
    if not user or not getattr(user, 'pk', None):
        return None
    return (
        Colaborador.objects.filter(usuario_id=user.pk)
        .select_related('usuario')
        .order_by('-ativo', '-pk')
        .first()
    )


def montar_contexto_app(user: User) -> dict[str, Any]:
    empresa = Empresa.objects.order_by('pk').first()
    colaborador = _colaborador_vinculado(user)

    empresa_payload: dict[str, Any] | None = None
    if empresa:
        empresa_payload = {
            'id': empresa.pk,
            'nome_exibicao': _nome_exibicao_empresa_header(empresa),
            'nome_curto': _nome_curto_empresa(empresa),
            'razao_social': empresa.razao_social,
            'cnpj': empresa.cnpj,
            'ambiente': resolver_ambiente_app(),
        }

    perfil = _perfil_label(user) if user.is_authenticated else ''
    if not perfil and user.is_authenticated:
        perfil = 'Consulta'

    nome_exibicao = resolver_nome_exibicao_usuario(user, colaborador)
    if colaborador and (colaborador.nome or '').strip():
        nome_exibicao = colaborador.nome.strip()
    colaborador_nome = (colaborador.nome or '').strip() if colaborador else ''

    email = user.email or ''
    email_tecnico = email_eh_tecnico_local(email)

    usuario_payload = {
        'id': user.pk,
        'nome': nome_exibicao,
        'nome_exibicao': nome_exibicao,
        'nome_curto': nome_curto_usuario(nome_exibicao),
        'email': email,
        'email_tecnico': email_tecnico,
        'username': user.username,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'perfil': perfil,
        'perfil_label': perfil,
        'is_admin': user.is_superuser or user.groups.filter(name__in=('admin', 'administrador')).exists(),
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'is_active': user.is_active,
        'colaborador_id': colaborador.pk if colaborador else None,
        'colaborador_nome': colaborador_nome,
    }

    colaborador_payload = None
    if colaborador:
        colaborador_payload = {
            'id': colaborador.pk,
            'nome': colaborador.nome,
            'codigo': colaborador.codigo or '',
            'email': colaborador.email or '',
            'telefone': colaborador.telefone or '',
            'cargo': colaborador.cargo or '',
            'departamento': colaborador.departamento or '',
            'ativo': colaborador.ativo,
            'funcoes_internas': _funcoes_colaborador(colaborador),
        }

    return {
        'empresa': empresa_payload,
        'usuario': usuario_payload,
        'colaborador': colaborador_payload,
        'ambiente': resolver_ambiente_app(),
        'ambiente_label': 'Homologação' if resolver_ambiente_app() == 'homologacao' else 'Produção',
    }


def montar_minha_conta(user: User) -> dict[str, Any]:
    ctx = montar_contexto_app(user)
    avisos: list[str] = []
    if ctx['usuario'].get('email_tecnico'):
        avisos.append(
            'Este e-mail parece ser técnico ou local. Para produção, informe um e-mail real.',
        )
    return {
        **ctx,
        'avisos': avisos,
    }
