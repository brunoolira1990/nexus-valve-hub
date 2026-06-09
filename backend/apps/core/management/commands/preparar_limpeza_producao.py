"""Comando de preparação para limpeza segura de dados de teste — ERP 4.0.14.9."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.limpeza_dados_teste import ambiente_atual, verificar_ambiente_seguro, LimpezaDadosTesteError
from apps.core.preparacao_limpeza_producao import (
    CONFIRMACAO_TOKEN,
    MSG_AVISO_EXECUCAO,
    MSG_PRODUTOS_BLOQUEIO,
    PreparacaoLimpezaError,
    executar_dry_run_limpeza_producao,
    executar_limpeza_producao,
    validar_execucao_limpeza_permitida,
)
from apps.core.prontidao_producao import executar_verificacao_prontidao


class Command(BaseCommand):
    help = (
        'Dry-run obrigatório para limpeza de dados operacionais de teste. '
        f'Execução: --executar --backup-confirmado --confirmar {CONFIRMACAO_TOKEN}'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Somente listar (padrão).')
        parser.add_argument('--executar', action='store_true', help='Executar limpeza real.')
        parser.add_argument(
            '--confirmar',
            type=str,
            default=None,
            help=f'Token obrigatório na execução: {CONFIRMACAO_TOKEN}',
        )
        parser.add_argument(
            '--backup-confirmado',
            action='store_true',
            help='Confirma que backup do banco/arquivos foi realizado.',
        )

    def handle(self, *args, **options):
        try:
            verificar_ambiente_seguro()
        except LimpezaDadosTesteError as exc:
            raise CommandError(str(exc)) from exc

        executar = bool(options.get('executar'))
        confirmar = (options.get('confirmar') or '').strip()
        backup_ok = bool(options.get('backup_confirmado'))

        rel = executar_dry_run_limpeza_producao()
        prontidao = executar_verificacao_prontidao()

        if not executar:
            self._imprimir_dry_run(rel, prontidao)
            self.stdout.write(
                self.style.WARNING(
                    f'\nPara executar: python manage.py preparar_limpeza_producao --executar '
                    f'--backup-confirmado --confirmar {CONFIRMACAO_TOKEN}',
                ),
            )
            return

        permitido, motivo = validar_execucao_limpeza_permitida(
            rel,
            prontidao,
            backup_confirmado=backup_ok,
            confirmacao=confirmar,
        )
        if not permitido:
            raise CommandError(motivo)

        self.stdout.write(self.style.WARNING(MSG_AVISO_EXECUCAO))

        try:
            removidos = executar_limpeza_producao(rel, prontidao=prontidao)
        except PreparacaoLimpezaError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('Limpeza concluída.'))
        self.stdout.write(f'Ambiente: {ambiente_atual() or "(padrão DEBUG)"}')
        for chave, qtd in removidos.items():
            self.stdout.write(f'  {chave}: {qtd} removido(s)')
        self.stdout.write(
            self.style.NOTICE(
                '\nRecomendado: python manage.py verificar_prontidao_producao && '
                'python manage.py preparar_limpeza_producao --dry-run',
            ),
        )

    def _imprimir_dry_run(self, rel: dict, prontidao: dict) -> None:
        self.stdout.write('[DRY-RUN] Preparação para limpeza de produção (ERP 4.0.14.9)\n')

        pp = rel.get('produtos_protegidos') or {}
        self.stdout.write(
            self.style.SUCCESS(
                f"Produtos preservados: {pp.get('total_preservados', rel.get('preservados', {}).get('produtos', 0))}",
            ),
        )
        if pp.get('candidatos_auditoria'):
            self.stdout.write(self.style.ERROR(f'  {MSG_PRODUTOS_BLOQUEIO}'))

        self.stdout.write('\nPreservados:')
        for chave, qtd in rel.get('preservados', {}).items():
            self.stdout.write(f'  {chave}: {qtd}')

        self.stdout.write('\nCandidatos à limpeza:')
        for chave, qtd in rel.get('candidatos_limpeza', {}).items():
            self.stdout.write(f'  {chave}: {qtd}')

        bloqueios = rel.get('bloqueios', {}).get('documentos_possivelmente_reais') or []
        self.stdout.write('\nBloqueios:')
        if bloqueios:
            for b in bloqueios:
                self.stdout.write(self.style.ERROR(f'  - {b}'))
        else:
            self.stdout.write('  (nenhum documento possivelmente real)')

        if prontidao.get('criticos'):
            self.stdout.write(self.style.ERROR('\nProntidão — críticos (bloqueiam execução):'))
            for c in prontidao['criticos']:
                self.stdout.write(self.style.ERROR(f"  - {c['mensagem']}"))

        self.stdout.write(self.style.SUCCESS('\nNenhum dado foi alterado (dry-run).'))
