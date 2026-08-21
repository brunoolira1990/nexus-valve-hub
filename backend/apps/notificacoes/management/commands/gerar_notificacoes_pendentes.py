from django.core.management.base import BaseCommand

from apps.notificacoes.events import gerar_notificacoes_pendentes


class Command(BaseCommand):
    help = 'Gera notificações internas para atividades, títulos e estoques pendentes.'

    def handle(self, *args, **options):
        resultado = gerar_notificacoes_pendentes()
        resumo = ', '.join(f'{chave}={valor}' for chave, valor in resultado.items())
        self.stdout.write(self.style.SUCCESS(f'Notificações processadas: {resumo}'))
