"""Recuperação administrativa de número NF-e Saída perdido no pool após descarte/exclusão local."""

from django.core.management.base import BaseCommand, CommandError

from apps.fiscal.nfe_emissao.numeracao_recuperacao_local import (
    CONFIRMACAO_TOKEN,
    analisar_recuperacao_numero_nfe_local,
    executar_recuperacao_numero_nfe_local,
    formatar_relatorio_recuperacao,
)


class Command(BaseCommand):
    help = (
        'Recupera número NF-e Saída para o pool NFeNumeracaoNumeroLiberado após descarte/exclusão '
        'local sem comunicação SEFAZ. Dry-run por padrão.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--empresa-id', type=int, required=True, help='ID da empresa emitente.')
        parser.add_argument('--serie', type=str, required=True, help='Série fiscal (ex.: 0, 1).')
        parser.add_argument(
            '--ambiente',
            type=str,
            required=True,
            choices=['homologacao', 'producao'],
            help='Ambiente fiscal (homologacao ou producao).',
        )
        parser.add_argument('--numero', type=int, required=True, help='Número fiscal a recuperar (ex.: 366).')
        parser.add_argument('--modelo', type=str, default='55', help='Modelo do documento (padrão: 55).')
        parser.add_argument(
            '--motivo',
            type=str,
            default='',
            help='Motivo da recuperação (mín. 10 caracteres; obrigatório para executar).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Somente exibir análise (padrão quando --confirmar não é informado).',
        )
        parser.add_argument(
            '--confirmar',
            type=str,
            default=None,
            help=f'Token de confirmação explícita: {CONFIRMACAO_TOKEN}',
        )

    def handle(self, *args, **options):
        empresa_id = options['empresa_id']
        serie = options['serie']
        ambiente = options['ambiente']
        numero = options['numero']
        modelo = options['modelo']
        motivo = options.get('motivo') or ''
        confirmar = (options.get('confirmar') or '').strip()
        executar = confirmar == CONFIRMACAO_TOKEN

        if confirmar and not executar:
            raise CommandError(
                f'Token de confirmação inválido. Use --confirmar {CONFIRMACAO_TOKEN}',
            )

        try:
            analise = analisar_recuperacao_numero_nfe_local(
                empresa_id=empresa_id,
                serie=serie,
                ambiente=ambiente,
                numero=numero,
                modelo=modelo,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(formatar_relatorio_recuperacao(analise))

        if not executar:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDry-run concluído. Para executar a recuperação:\n'
                    f'  python manage.py recuperar_numero_nfe_local '
                    f'--empresa-id {empresa_id} --serie {serie} --ambiente {ambiente} '
                    f'--numero {numero} --motivo "Motivo detalhado aqui" '
                    f'--confirmar {CONFIRMACAO_TOKEN}',
                ),
            )
            return

        if not analise.seguro:
            raise CommandError(analise.mensagem)

        if analise.ja_no_pool:
            self.stdout.write(self.style.WARNING('\nNúmero já está no pool. Nada foi alterado.'))
            return

        try:
            resultado = executar_recuperacao_numero_nfe_local(
                empresa_id=empresa_id,
                serie=serie,
                ambiente=ambiente,
                numero=numero,
                modelo=modelo,
                motivo=motivo,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if not resultado.get('executado'):
            self.stdout.write(self.style.WARNING(f'\n{resultado.get("mensagem", "Nada executado.")}'))
            return

        self.stdout.write(self.style.SUCCESS('\nRecuperação concluída.'))
        self.stdout.write(f'  Pool ID: {resultado.get("pool_id")}')
        if resultado.get('nfe_origem_excluida'):
            self.stdout.write(
                '  NF-e origem não encontrada — entrada criada sem vínculo de origem '
                '(exclusão física anterior).'
            )
