"""
Cria um superutilizador de desenvolvimento se ainda não existir (idempotente).
Controlado por DJANGO_CREATE_DEV_USER (predefinição: ativo).

Uso manual:
  python manage.py criar_usuario_inicial
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


def _env_flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


class Command(BaseCommand):
    help = "Garante um superuser de dev (credenciais via env; não sobrescreve se já existir)."

    def handle(self, *args, **options):
        if not _env_flag("DJANGO_CREATE_DEV_USER", "1"):
            self.stdout.write("criar_usuario_inicial: ignorado (DJANGO_CREATE_DEV_USER desativado).")
            return

        username = os.environ.get("DJANGO_DEV_USERNAME", "admin").strip() or "admin"
        password = os.environ.get("DJANGO_DEV_PASSWORD", "admin123")
        email = os.environ.get("DJANGO_DEV_EMAIL", "admin@localhost").strip() or f"{username}@localhost"

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"Utilizador «{username}» já existe; nada a fazer."))
            return

        User.objects.create_superuser(username, email, password)
        self.stdout.write(self.style.SUCCESS(f"Superuser «{username}» criado (login JWT + /admin/)."))
