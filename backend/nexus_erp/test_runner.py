"""Test runner com verificação de banco isolado — ERP 4.0.13.7.2."""

from __future__ import annotations

import os

from django.db import connection
from django.test.runner import DiscoverRunner


class NexusDiscoverRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        result = super().setup_databases(**kwargs)
        if os.environ.get('NEXUS_ALLOW_DEV_DB_TESTS') == '1':
            return result
        db_name = connection.settings_dict.get('NAME') or ''
        if not db_name.startswith('test_'):
            raise RuntimeError(
                f'Testes bloqueados: conexão ativa "{db_name}" não é banco isolado (test_*). '
                'Execute via `python manage.py test` sem reutilizar o banco de desenvolvimento.',
            )
        return result
