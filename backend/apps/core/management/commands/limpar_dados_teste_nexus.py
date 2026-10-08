"""Comando de higienização segura de dados de teste/dev (ERP 4.0.13.5.2)."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.limpeza_dados_teste import (
    CONFIRMACAO_TOKEN,
    LimpezaDadosTesteError,
    ambiente_atual,
    executar_dry_run,
    executar_limpeza_confirmada,
    imprimir_relatorio_dry_run,
    salvar_relatorio_dry_run,
    verificar_ambiente_seguro,
)


class Command(BaseCommand):
    help = (
        'Identifica e remove dados de teste/dev com dry-run obrigatório por padrão. '
        f'Execução: --confirmar {CONFIRMACAO_TOKEN}'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Somente listar candidatos (padrão quando não há confirmação).',
        )
        parser.add_argument(
            '--confirmar',
            type=str,
            default=None,
            help=f'Token de confirmação explícita: {CONFIRMACAO_TOKEN}',
        )
        parser.add_argument('--clientes', action='store_true', help='Reservado: filtrar só clientes.')
        parser.add_argument('--produtos', action='store_true', help='Reservado: filtrar só produtos.')
        parser.add_argument('--pedidos', action='store_true', help='Reservado: filtrar só pedidos.')
        parser.add_argument('--nfe', action='store_true', help='Reservado: filtrar só NF-e.')
        parser.add_argument('--somente-padroes-obvios', action='store_true', help='Reservado: critérios mais restritos.')
        parser.add_argument('--criado-apos', type=str, default=None, help='Reservado: filtro por data.')
        parser.add_argument('--empresa-id', type=int, default=None, help='Reservado: filtro por empresa.')

    def handle(self, *args, **options):
        try:
            verificar_ambiente_seguro()
        except LimpezaDadosTesteError as exc:
            raise CommandError(str(exc)) from exc

        confirmar = (options.get('confirmar') or '').strip()
        executar = confirmar == CONFIRMACAO_TOKEN
        if confirmar and not executar:
            raise CommandError(
                f'Token de confirmação inválido. Use --confirmar {CONFIRMACAO_TOKEN}',
            )

        rel = executar_dry_run()

        if not executar:
            imprimir_relatorio_dry_run(rel, self.stdout.write)
            json_path, csv_path = salvar_relatorio_dry_run(rel)
            self.stdout.write(self.style.SUCCESS(f'\nRelatório JSON: {json_path}'))
            if csv_path:
                self.stdout.write(f'Relatório CSV: {csv_path}')
            self.stdout.write(
                self.style.WARNING(
                    f'\nPara executar a limpeza: python manage.py limpar_dados_teste_nexus '
                    f'--confirmar {CONFIRMACAO_TOKEN}',
                ),
            )
            return

        try:
            removidos = executar_limpeza_confirmada(rel)
        except LimpezaDadosTesteError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('Limpeza concluída.'))
        self.stdout.write(f'Ambiente: {ambiente_atual() or "(padrão DEBUG)"}')
        for chave, qtd in removidos.items():
            self.stdout.write(f'  {chave}: {qtd} removido(s)')
