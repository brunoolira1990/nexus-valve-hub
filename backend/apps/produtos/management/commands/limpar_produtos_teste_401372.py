"""Remove produtos artificiais de teste — ERP 4.0.13.7.2 (dry-run por padrão)."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.limpeza_dados_teste import LimpezaDadosTesteError, verificar_ambiente_seguro
from apps.produtos.limpeza_produtos_teste_401372 import (
    CONFIRMACAO_TOKEN,
    LimpezaProdutosTesteError,
    executar_dry_run_produtos_teste,
    executar_limpeza_confirmada,
    imprimir_relatorio_dry_run,
)


class Command(BaseCommand):
    help = (
        'Identifica e remove produtos artificiais listados (descrição "Fam", códigos N*). '
        f'Dry-run por padrão. Remoção: --confirmar {CONFIRMACAO_TOKEN}'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            type=str,
            default=None,
            help=f'Token de confirmação explícita: {CONFIRMACAO_TOKEN}',
        )

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

        relatorio = executar_dry_run_produtos_teste()
        imprimir_relatorio_dry_run(relatorio, self.stdout.write)

        if not executar:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDry-run concluído. Para remover: python manage.py limpar_produtos_teste_401372 '
                    f'--confirmar {CONFIRMACAO_TOKEN}',
                ),
            )
            return

        try:
            resultado = executar_limpeza_confirmada(relatorio)
        except LimpezaProdutosTesteError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('\nLimpeza concluída.'))
        self.stdout.write(f"  Removidos: {resultado['total_removidos']}")
        if resultado.get('total_familias_removidas'):
            self.stdout.write(f"    Famílias de teste: {resultado['total_familias_removidas']}")
        if resultado.get('total_produtos_removidos'):
            self.stdout.write(f"    Produtos: {resultado['total_produtos_removidos']}")
        for item in resultado.get('removidos', []):
            ref = item.get('familia_id') or item.get('produto_id')
            self.stdout.write(f"    - [{item.get('tipo', 'produto')}] {item['codigo']} (id={ref})")
        if resultado.get('protegidos_na_execucao'):
            self.stdout.write(self.style.WARNING('  Protegidos na execução (vínculo detectado):'))
            for item in resultado['protegidos_na_execucao']:
                self.stdout.write(f"    - {item['codigo']} — {', '.join(item.get('vinculos') or [])}")
