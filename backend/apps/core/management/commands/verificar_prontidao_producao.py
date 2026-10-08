"""Comando de verificação de prontidão para produção — ERP 4.0.14.9 (somente leitura)."""

from django.core.management.base import BaseCommand

from apps.core.prontidao_producao import executar_verificacao_prontidao


class Command(BaseCommand):
    help = 'Verifica prontidão para produção (somente leitura, sem alterações).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Alias explícito — o comando sempre é somente leitura.',
        )

    def handle(self, *args, **options):
        rel = executar_verificacao_prontidao()

        self.stdout.write('=== PRONTIDÃO PARA PRODUÇÃO (ERP 4.0.14.9) ===\n')
        self.stdout.write('Preservados / contagens:')
        for chave, qtd in rel['preservados'].items():
            self.stdout.write(f'  {chave}: {qtd}')

        self.stdout.write('\nCríticos:')
        if rel['criticos']:
            for item in rel['criticos']:
                self.stdout.write(self.style.ERROR(f"  - {item['mensagem']}"))
        else:
            self.stdout.write(self.style.SUCCESS('  (nenhum)'))

        self.stdout.write('\nAvisos:')
        if rel['avisos']:
            for item in rel['avisos']:
                self.stdout.write(self.style.WARNING(f"  - {item['mensagem']}"))
        else:
            self.stdout.write('  (nenhum)')

        self.stdout.write('\nItens OK:')
        if rel.get('ok'):
            for item in rel['ok']:
                self.stdout.write(self.style.SUCCESS(f"  - {item['mensagem']}"))
        else:
            self.stdout.write('  (nenhum)')

        self.stdout.write('\nChecklist de produção:')
        for row in rel['checklist_producao']:
            mark = 'OK' if row['ok'] else 'PENDENTE'
            style = self.style.SUCCESS if row['ok'] else self.style.WARNING
            nota = f" — {row['nota']}" if row.get('nota') else ''
            self.stdout.write(style(f"  [{mark}] {row['item']}{nota}"))

        if rel['pronto']:
            self.stdout.write(self.style.SUCCESS('\nNenhum erro crítico bloqueante.'))
        else:
            self.stdout.write(self.style.ERROR('\nCorrija os itens críticos antes de produção.'))

        self.stdout.write(self.style.NOTICE('\nNenhum dado foi alterado (somente leitura).'))
