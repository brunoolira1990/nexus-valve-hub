#!/usr/bin/env python3
"""
Aguarda o PostgreSQL ficar disponível antes de iniciar o Django.

Usado no startup do container backend: quando o Docker reinicia só o backend
(restart: unless-stopped), depends_on/condition: service_healthy do Compose
não é reavaliado — este script evita crash-loop por banco ainda indisponível.
"""

from __future__ import annotations

import os
import sys
import time

import psycopg2


def _db_params() -> dict[str, str | int]:
    return {
        'host': os.environ.get('DB_HOST') or os.environ.get('POSTGRES_HOST', 'db'),
        'port': int(os.environ.get('DB_PORT') or os.environ.get('POSTGRES_PORT', '5432')),
        'dbname': os.environ.get('DB_NAME') or os.environ.get('POSTGRES_DB', 'nexus_erp'),
        'user': os.environ.get('DB_USER') or os.environ.get('POSTGRES_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD') or os.environ.get('POSTGRES_PASSWORD', 'postgres'),
    }


def main() -> int:
    params = _db_params()
    max_wait = int(os.environ.get('DB_WAIT_MAX_SECONDS', '90'))
    delay = 1
    max_delay = 8
    elapsed = 0
    attempt = 0

    host = str(params['host'])
    port = int(params['port'])

    print(
        f'[wait_for_db] Aguardando PostgreSQL em {host}:{port} '
        f'(até {max_wait}s, backoff exponencial)...',
        flush=True,
    )

    while elapsed < max_wait:
        attempt += 1
        try:
            conn = psycopg2.connect(connect_timeout=3, **params)
            conn.close()
            print(
                f'[wait_for_db] PostgreSQL disponível após {elapsed}s (tentativa {attempt}).',
                flush=True,
            )
            return 0
        except psycopg2.OperationalError as exc:
            msg = str(exc).splitlines()[0]
            print(
                f'[wait_for_db] Tentativa {attempt} ({elapsed}s/{max_wait}s): {msg}',
                flush=True,
            )
            time.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, max_delay)

    print(
        f'[wait_for_db] PostgreSQL indisponível após {max_wait}s em {host}:{port}.',
        file=sys.stderr,
        flush=True,
    )
    return 1


if __name__ == '__main__':
    sys.exit(main())
