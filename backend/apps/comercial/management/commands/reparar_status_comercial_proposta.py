"""Reparo controlado de itens de proposta presos após exclusão de pedido (pré-hotfix)."""

from django.core.management.base import BaseCommand, CommandError

from apps.comercial.models import Proposta
from apps.comercial.reparar_status_comercial_proposta import (
    CONFIRMACAO_TOKEN,
    analisar_reparo_status_comercial_proposta,
    executar_reparo_status_comercial_proposta,
    formatar_relatorio_reparo,
)


class Command(BaseCommand):
    help = (
        'Repara itens órfãos de proposta com status CONVERTIDO_EM_PEDIDO após exclusão '
        'de pedido anterior ao hotfix. Dry-run por padrão.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--proposta-id',
            type=int,
            required=True,
            help='ID da proposta a analisar/reparar.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Somente exibir o que seria reparado (padrão quando --confirmar não é informado).',
        )
        parser.add_argument(
            '--confirmar',
            type=str,
            default=None,
            help=f'Token de confirmação explícita: {CONFIRMACAO_TOKEN}',
        )

    def handle(self, *args, **options):
        proposta_id = options['proposta_id']
        confirmar = (options.get('confirmar') or '').strip()
        executar = confirmar == CONFIRMACAO_TOKEN

        if confirmar and not executar:
            raise CommandError(
                f'Token de confirmação inválido. Use --confirmar {CONFIRMACAO_TOKEN}',
            )

        try:
            proposta = Proposta.objects.get(pk=proposta_id)
        except Proposta.DoesNotExist as exc:
            raise CommandError(f'Proposta id={proposta_id} não encontrada.') from exc

        relatorio = analisar_reparo_status_comercial_proposta(proposta)
        self.stdout.write(formatar_relatorio_reparo(relatorio))

        if not executar:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDry-run concluído. Para executar o reparo:\n'
                    f'  python manage.py reparar_status_comercial_proposta '
                    f'--proposta-id {proposta_id} --confirmar {CONFIRMACAO_TOKEN}',
                ),
            )
            return

        if not relatorio.itens_reparaveis:
            self.stdout.write(self.style.WARNING('\nNenhum item reparável encontrado. Nada foi alterado.'))
            return

        try:
            resultado = executar_reparo_status_comercial_proposta(proposta)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('\nReparo concluído.'))
        self.stdout.write(f"  Itens reparados: {len(resultado['itens_reparados'])}")
        self.stdout.write(f"  Status: {resultado['status_anterior']} → {resultado['status_novo']}")
        for item in resultado['itens_reparados']:
            ref = item.get('pedido_numero_ref') or item.get('pedido_id_ref') or '—'
            self.stdout.write(f"    - Item #{item['item_proposta_id']} (pedido ref: {ref})")
