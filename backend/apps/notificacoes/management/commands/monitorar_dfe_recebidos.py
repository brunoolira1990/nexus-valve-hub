from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.cadastros.models import Empresa
from apps.fiscal.dfe_recebidos.captura_sefaz import capturar_dfe_recebidos_sefaz
from apps.notificacoes.events import (
    gerar_notificacoes_pendentes,
    notificar_falha_captura_dfe,
    notificar_pendencia_captura_dfe,
)


class Command(BaseCommand):
    help = (
        'Consulta incremental de NF-e/CT-e recebidos na SEFAZ e cria notificações internas; '
        'não manifesta, baixa XML nem lança documentos.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa-id',
            type=int,
            default=None,
            help='Monitora somente a empresa informada.',
        )
        parser.add_argument(
            '--limite-lotes',
            type=int,
            default=3,
            help='Máximo de lotes por tipo nesta execução (1 a 20).',
        )

    def handle(self, *args, **options):
        empresa_id = options.get('empresa_id')
        limite_lotes = max(1, min(int(options.get('limite_lotes') or 3), 20))
        empresas = Empresa.objects.filter(nfe_ambiente=Empresa.NfeAmbiente.PRODUCAO).order_by('pk')
        if empresa_id:
            empresas = empresas.filter(pk=empresa_id)

        total_notificacoes = 0
        processadas = 0
        falhas = 0
        for empresa in empresas.iterator():
            processadas += 1
            resultado = capturar_dfe_recebidos_sefaz(
                empresa_id=empresa.pk,
                tipos=['NFE', 'CTE'],
                modo='incremental',
                limite_lotes=limite_lotes,
            )
            total_notificacoes += int(resultado.get('notificacoes_fiscais_criadas') or 0)
            total_notificacoes += len(notificar_falha_captura_dfe(empresa.pk, resultado))
            total_notificacoes += len(notificar_pendencia_captura_dfe(empresa.pk, resultado))
            if resultado.get('sucesso'):
                resumo = resultado.get('resumo') or {}
                self.stdout.write(
                    self.style.SUCCESS(
                        f'empresa={empresa.pk} nfe_novas={resumo.get("nfe_novas", 0)} '
                        f'cte_novos={resumo.get("cte_novos", 0)} '
                        f'notificacoes={resultado.get("notificacoes_fiscais_criadas", 0)}',
                    ),
                )
            else:
                falhas += 1
                erros = '; '.join(str(item) for item in (resultado.get('erros') or []))
                self.stderr.write(
                    self.style.WARNING(
                        f'empresa={empresa.pk} captura não concluída: {erros or "motivo não informado"}',
                    ),
                )

        pendentes = gerar_notificacoes_pendentes()
        total_notificacoes += sum(pendentes.values())
        self.stdout.write(
            f'monitoramento concluído: empresas={processadas} falhas={falhas} '
            f'notificacoes_total={total_notificacoes} pendentes={pendentes}',
        )
        if falhas and processadas:
            self.stderr.write('Uma ou mais empresas não puderam ser consultadas; verifique os avisos acima.')
            return
        if not processadas:
            self.stdout.write('Nenhuma empresa em produção foi encontrada para monitoramento.')
