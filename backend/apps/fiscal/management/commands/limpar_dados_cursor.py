"""Limpeza confirmada de dados Cursor/teste."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.fiscal.limpeza_cursor.limpeza import (
    LimpezaCursorError,
    carregar_relatorio_auditoria,
    executar_limpeza_cursor,
    verificar_backup_existe,
)


class Command(BaseCommand):
    help = 'Remove dados Cursor/teste após backup e confirmação explícita.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma execução da limpeza (obrigatório).',
        )
        parser.add_argument(
            '--arquivo-dry-run',
            type=str,
            required=True,
            help='JSON gerado por auditoria_limpeza_cursor --dry-run',
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            raise CommandError('Use --confirmar para executar a limpeza.')

        backup = verificar_backup_existe()
        if backup is None:
            raise CommandError(
                'Nenhum backup encontrado em media/backups/limpeza_cursor/. '
                'Execute: python manage.py backup_limpeza_cursor',
            )

        path = Path(options['arquivo_dry_run'])
        rel = carregar_relatorio_auditoria(path)

        try:
            removidos = executar_limpeza_cursor(rel)
        except LimpezaCursorError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('Limpeza concluída.'))
        for k, v in removidos.items():
            self.stdout.write(f'  {k}: {v} removido(s)')
        self.stdout.write(f'Backup utilizado: {backup}')
