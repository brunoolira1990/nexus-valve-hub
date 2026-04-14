from django.core.management.base import BaseCommand

from apps.produtos.models import Ncm


class Command(BaseCommand):
    help = 'Insere alguns NCMs de exemplo (opcional).'

    def handle(self, *args, **options):
        exemplos = [
            ('8481.80.99', 'Válvulas, torneiras e dispositivos semelhantes'),
            ('7307.99.00', 'Outras obras de ferro ou aço'),
        ]
        for codigo, desc in exemplos:
            Ncm.objects.update_or_create(codigo=codigo, defaults={'descricao': desc})
        self.stdout.write(self.style.SUCCESS(f'NCMs de exemplo garantidos ({len(exemplos)} registros).'))
