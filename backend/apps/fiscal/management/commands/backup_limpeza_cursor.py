"""Backup/export antes da limpeza de dados Cursor."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor
from apps.fiscal.limpeza_cursor.backup import exportar_backup_limpeza_cursor
from apps.fiscal.limpeza_cursor.limpeza import carregar_relatorio_auditoria


class Command(BaseCommand):
    help = 'Exporta backup CSV/JSON dos candidatos à limpeza Cursor (obrigatório antes de limpar).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--arquivo-auditoria',
            type=str,
            default='',
            help='JSON de auditoria dry-run (opcional; gera novo se omitido).',
        )

    def handle(self, *args, **options):
        arq = (options.get('arquivo_auditoria') or '').strip()
        if arq:
            rel = carregar_relatorio_auditoria(Path(arq))
        else:
            rel = executar_auditoria_limpeza_cursor()
        try:
            dest = exportar_backup_limpeza_cursor(rel)
        except Exception as exc:
            raise CommandError(f'Falha no backup: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(f'Backup salvo em: {dest}'))
