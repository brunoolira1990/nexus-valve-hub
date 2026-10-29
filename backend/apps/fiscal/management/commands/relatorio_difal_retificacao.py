"""Relatório de retificação DIFAL — audita NF-e emitidas com base única antes do deploy do fix."""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import ProgrammingError

from apps.fiscal.difal_retificacao import (
    CFOP_DIFAL_DEVIDO,
    analisar_difal_retificacao,
    formatar_relatorio_difal_retificacao,
)


class Command(BaseCommand):
    help = (
        'Lista NF-e de saída autorizadas (produção) com DIFAL emitido × DIFAL correto pela tabela de '
        'alíquotas por UF, filtrando só o DIFAL devido (CFOP 6108 + destinatário não contribuinte). '
        'Somente leitura — destina-se à auditoria de retificação.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--desde', type=str, default='', help='Data inicial AAAA-MM-DD (ex.: 2026-01-01).')
        parser.add_argument('--ate', type=str, default='', help='Data final AAAA-MM-DD (opcional).')
        parser.add_argument(
            '--cfop',
            type=str,
            default='',
            help=(
                'CFOPs com DIFAL devido, separados por vírgula (ex.: 6108,6107). '
                'Vazio = só 6108.'
            ),
        )
        parser.add_argument(
            '--excluir-uf-origem',
            type=str,
            default='',
            help='Exclui NF-e emitidas desta UF (ex.: SP = só vendas para fora de SP). Vazio = todas.',
        )

    def handle(self, *args, **options):
        def _parse_data(valor: str, rotulo: str):
            if not valor:
                return None
            try:
                return datetime.strptime(valor.strip(), '%Y-%m-%d').date()
            except ValueError as exc:
                raise CommandError(f'{rotulo} inválido: use AAAA-MM-DD.') from exc

        desde = _parse_data(options['desde'], '--desde')
        ate = _parse_data(options['ate'], '--ate')
        uf_exclusao = (options['excluir_uf_origem'] or '').strip().upper()[:2] or None
        if uf_exclusao and len(uf_exclusao) != 2:
            raise CommandError('--excluir-uf-origem deve ter 2 caracteres (ex.: SP).')
        cfops = [c.strip() for c in (options['cfop'] or '').replace(';', ',').split(',') if c.strip()]
        cfop_invalido = [c for c in cfops if not (c.isdigit() and len(c) == 4)]
        if cfop_invalido:
            raise CommandError(f'--cfop inválido: {", ".join(cfop_invalido)} — use 4 dígitos (ex.: 6108).')

        try:
            relatorio = analisar_difal_retificacao(
                desde=desde,
                ate=ate,
                uf_exclusao_origem=uf_exclusao,
                cfops_devidos=cfops or CFOP_DIFAL_DEVIDO,
            )
        except ProgrammingError as exc:
            raise CommandError(
                'Tabela de alíquotas por UF indisponível — aplique as migrations '
                'regras_fiscais 0015 a 0018 antes de auditar o DIFAL.'
            ) from exc
        self.stdout.write(formatar_relatorio_difal_retificacao(relatorio))
        if relatorio.nf_divergentes:
            self.stdout.write(
                self.style.WARNING(
                    f'\n{relatorio.nf_divergentes} NF-e exigem avaliação de retificação '
                    '(NF-e de ajuste ou estorno conforme convenção da SEFAZ).'
                ),
            )
