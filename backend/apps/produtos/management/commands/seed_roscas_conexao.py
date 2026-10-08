"""Garante o catálogo canônico de roscas/conexões (incl. SW)."""

from django.core.management.base import BaseCommand

from apps.produtos.roscas_conexao_base import ROSCAS_CONEXAO_CANONICAS, seed_roscas_conexao_canonicas


class Command(BaseCommand):
    help = 'Popula roscas/conexões canônicas (idempotente; inclui SW).'

    def handle(self, *args, **options):
        seed_roscas_conexao_canonicas()
        self.stdout.write(
            self.style.SUCCESS(f'Roscas / conexões: {len(ROSCAS_CONEXAO_CANONICAS)} opções canônicas garantidas.'),
        )
