from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.produtos.models import Polegada
from apps.produtos.polegadas import aliases_for_polegada, parse_polegada_to_decimal

POLEGADAS_OFICIAIS = [
    ('01', '1/8"'),
    ('02', '1/4"'),
    ('03', '3/8"'),
    ('04', '1/2"'),
    ('05', '3/4"'),
    ('06', '1"'),
    ('07', '1.1/4"'),
    ('08', '1.1/2"'),
    ('09', '2"'),
    ('10', '2.1/4"'),
    ('11', '2.1/2"'),
    ('12', '3"'),
    ('13', '3.1/4"'),
    ('14', '3.1/2"'),
    ('15', '4"'),
    ('16', '5"'),
    ('17', '6"'),
    ('18', '6.1/4"'),
    ('19', '8"'),
    ('20', '10"'),
    ('21', '12"'),
    ('22', '14"'),
    ('23', '16"'),
    ('24', '18"'),
    ('25', '20"'),
    ('26', '22"'),
    ('27', '24"'),
    ('28', '26"'),
    ('29', '28"'),
    ('30', '30"'),
    ('31', '32"'),
    ('32', '34"'),
    ('33', '36"'),
    ('34', '38"'),
    ('35', '40"'),
    ('36', '42"'),
    ('37', '44"'),
    ('38', '46"'),
    ('39', '48"'),
    ('40', '2.3/4"'),
]


class Command(BaseCommand):
    help = 'Popula a tabela Polegada com códigos oficiais 01–40 e descrições legíveis.'

    def handle(self, *args, **options):
        for codigo, descricao in POLEGADAS_OFICIAIS:
            dec = parse_polegada_to_decimal(descricao) or Decimal('0')
            mm = (dec * Decimal('25.4')).quantize(Decimal('0.001'))
            Polegada.objects.update_or_create(
                codigo_oficial=codigo,
                defaults={
                    'codigo': codigo,
                    'descricao': descricao,
                    'valor_decimal': dec,
                    'valor_mm': mm,
                    'aliases': aliases_for_polegada(descricao, dec, mm),
                    'ativo': True,
                    'origem': 'SEED_LEGADO',
                },
            )
        self.stdout.write(self.style.SUCCESS(f'Polegadas: {len(POLEGADAS_OFICIAIS)} registros garantidos.'))
