from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Popula medidas OD (polegada real) com conversão mm.'

    def handle(self, *args, **options):
        call_command('seed_polegadas_base_21')
