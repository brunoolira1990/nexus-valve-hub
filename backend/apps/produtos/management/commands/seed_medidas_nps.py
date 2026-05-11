from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Popula medidas NPS nominais com códigos históricos Nexus.'

    def handle(self, *args, **options):
        call_command('seed_polegadas')
