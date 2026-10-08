"""Guarda banco isolado para testes automatizados — ERP 4.0.13.7.2."""

from __future__ import annotations

import os

from django.db import connection


def banco_teste_isolado() -> bool:
    """True quando a conexão ativa é um banco de teste Django (prefixo test_)."""
    name = (connection.settings_dict.get('NAME') or '').strip()
    return name.startswith('test_')


def assert_banco_teste_isolado() -> None:
    """Impede testes de persistirem dados no banco de desenvolvimento."""
    if os.environ.get('NEXUS_ALLOW_DEV_DB_TESTS') == '1':
        return
    name = connection.settings_dict.get('NAME') or ''
    if not banco_teste_isolado():
        raise RuntimeError(
            f'Testes bloqueados no banco "{name}". '
            'Use `python manage.py test` (banco test_*) ou defina NEXUS_ALLOW_DEV_DB_TESTS=1 '
            'somente em ambiente controlado.',
        )
