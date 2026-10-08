"""Dry-run: auditoria de dados Cursor/teste sem exclusão."""

from django.core.management.base import BaseCommand

from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor, salvar_relatorio_auditoria


class Command(BaseCommand):
    help = 'Lista candidatos à limpeza de dados Cursor/teste (dry-run, sem apagar).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=True,
            help='Somente auditoria (padrão).',
        )

    def handle(self, *args, **options):
        rel = executar_auditoria_limpeza_cursor()
        json_path, csv_path = salvar_relatorio_auditoria(rel)
        res = rel['resumo']
        self.stdout.write(self.style.SUCCESS('Auditoria dry-run concluída.'))
        self.stdout.write(f"Empresas candidatas: {res['empresas_candidatas']}")
        self.stdout.write(f"Clientes candidatos: {res['clientes_candidatos']}")
        self.stdout.write(f"Pedidos candidatos: {res['pedidos_candidatos']}")
        self.stdout.write(f"NF-e candidatas: {res['nfe_candidatas']}")
        self.stdout.write(f"Faturamentos candidatos: {res['faturamentos_candidatos']}")
        self.stdout.write(f"Produtos para revisão: {res['produtos_revisao']}")
        self.stdout.write(f"NF-e preservadas: {res['preservados_nfe']}")
        self.stdout.write(f'JSON: {json_path}')
        if csv_path:
            self.stdout.write(f'CSV: {csv_path}')
