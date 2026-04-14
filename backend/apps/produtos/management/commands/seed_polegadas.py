from django.core.management.base import BaseCommand

from apps.produtos.models import Polegada


def _desc_inches(index: int) -> str:
    """Interpola entre 1/8\" e 48\" (48 posições, IDs 01–48)."""
    start = 0.125
    end = 48.0
    if index <= 1:
        inches = start
    else:
        inches = start + (end - start) * (index - 1) / 47
    if inches == int(inches):
        return f'{int(inches)}"'
    return f'{inches:.3f}"'.rstrip('0').rstrip('.') + '"'


class Command(BaseCommand):
    help = 'Popula Polegada com 48 registros (códigos 01 a 48).'

    def handle(self, *args, **options):
        created = 0
        for i in range(1, 49):
            codigo = f'{i:02d}'
            descricao = _desc_inches(i)
            _, was_created = Polegada.objects.update_or_create(
                codigo=codigo,
                defaults={'descricao': descricao},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Polegadas: {created} criadas/atualizadas (total 48).'))
