"""Gera relatório consolidado de pré-produção — ERP 4.0.14.9 (somente leitura)."""

import getpass

from django.core.management.base import BaseCommand

from apps.core.pre_producao import gerar_relatorio_pre_producao, salvar_relatorio_pre_producao


class Command(BaseCommand):
    help = 'Gera relatório JSON de pré-produção (prontidão + dry-run, sem alterar dados).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usuario',
            type=str,
            default='',
            help='Identificação do executor (padrão: usuário do SO).',
        )
        parser.add_argument(
            '--saida',
            type=str,
            default='',
            help='Caminho opcional do JSON (padrão: reports/pre_producao_YYYYMMDD_HHMMSS.json).',
        )

    def handle(self, *args, **options):
        usuario = (options.get('usuario') or '').strip() or getpass.getuser()
        rel = gerar_relatorio_pre_producao(usuario_executor=usuario)

        saida = (options.get('saida') or '').strip()
        if saida:
            from pathlib import Path
            path = Path(saida)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                __import__('json').dumps(rel, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        else:
            path = salvar_relatorio_pre_producao(rel)

        self.stdout.write('=== RELATÓRIO DE PRÉ-PRODUÇÃO (ERP 4.0.14.9) ===\n')
        self.stdout.write(f'Arquivo: {path}')
        self.stdout.write(f"Ambiente: {rel.get('ambiente')}")
        self.stdout.write(f"Prontidão pronta: {rel['prontidao']['pronto']}")
        self.stdout.write(f"Críticos: {len(rel['prontidao']['criticos'])}")
        self.stdout.write(f"Avisos: {len(rel['prontidao']['avisos'])}")
        pp = rel['dry_run_limpeza'].get('produtos_protegidos', {})
        self.stdout.write(f"Produtos preservados: {pp.get('total_preservados', '—')}")
        self.stdout.write(f"Execução limpeza permitida agora: {rel['execucao_limpeza']['permitida_agora']}")
        if rel['execucao_limpeza'].get('motivo_bloqueio'):
            self.stdout.write(self.style.WARNING(f"Bloqueio: {rel['execucao_limpeza']['motivo_bloqueio']}"))
        self.stdout.write(self.style.SUCCESS('\nNenhum dado foi alterado.'))
