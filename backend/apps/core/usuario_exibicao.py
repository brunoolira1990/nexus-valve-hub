"""Nome exibido e e-mail — ERP 4.0.14.9.4."""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model

from apps.cadastros.colaborador_senha import email_operacional_valido
from apps.cadastros.models import Colaborador

User = get_user_model()

DOMINIOS_EMAIL_TECNICO = frozenset(
    {
        'localhost',
        'local',
        'localdomain',
        'test',
        'example.com',
        'example.org',
        'invalid',
    },
)


def email_eh_tecnico_local(email: str) -> bool:
    valor = (email or '').strip().lower()
    if not valor:
        return True
    if '@' not in valor:
        return True
    _, _, domain = valor.partition('@')
    if domain in DOMINIOS_EMAIL_TECNICO:
        return True
    if domain.endswith('.local') or domain.endswith('.localhost') or domain.endswith('.test'):
        return True
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
        return True
    return not email_operacional_valido(valor)


def resolver_nome_exibicao_usuario(user: User, colaborador: Colaborador | None = None) -> str:
    if colaborador and (colaborador.nome or '').strip():
        return colaborador.nome.strip()
    nome_completo = f'{user.first_name or ""} {user.last_name or ""}'.strip()
    if nome_completo:
        return nome_completo
    return (user.username or '').strip() or 'Usuário'


def nome_curto_usuario(nome_exibicao: str, max_len: int = 18) -> str:
    """Primeiro nome ou abreviação para telas estreitas."""
    partes = (nome_exibicao or '').split()
    if not partes:
        return 'Usuário'
    if len(partes) == 1:
        return partes[0][:max_len]
    return f'{partes[0]} {partes[-1][0]}.'.strip()[:max_len]
