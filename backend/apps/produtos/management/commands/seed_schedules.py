from django.core.management.base import BaseCommand

from apps.produtos.models import ScheduleEspessura


SCHEDULES_BASE = [
    ('5', 'SCH 5', ScheduleEspessura.Aplicacao.CARBONO, 10),
    ('10', 'SCH 10', ScheduleEspessura.Aplicacao.CARBONO, 20),
    ('20', 'SCH 20', ScheduleEspessura.Aplicacao.CARBONO, 30),
    ('30', 'SCH 30', ScheduleEspessura.Aplicacao.CARBONO, 40),
    ('40', 'SCH 40', ScheduleEspessura.Aplicacao.CARBONO, 50),
    ('60', 'SCH 60', ScheduleEspessura.Aplicacao.CARBONO, 60),
    ('80', 'SCH 80', ScheduleEspessura.Aplicacao.CARBONO, 70),
    ('100', 'SCH 100', ScheduleEspessura.Aplicacao.CARBONO, 80),
    ('120', 'SCH 120', ScheduleEspessura.Aplicacao.CARBONO, 90),
    ('140', 'SCH 140', ScheduleEspessura.Aplicacao.CARBONO, 100),
    ('160', 'SCH 160', ScheduleEspessura.Aplicacao.CARBONO, 110),
    ('STD', 'STD', ScheduleEspessura.Aplicacao.AMBOS, 120),
    ('XS', 'XS', ScheduleEspessura.Aplicacao.AMBOS, 130),
    ('XXS', 'XXS', ScheduleEspessura.Aplicacao.AMBOS, 140),
    ('5S', 'SCH 5S', ScheduleEspessura.Aplicacao.INOX, 150),
    ('10S', 'SCH 10S', ScheduleEspessura.Aplicacao.INOX, 160),
    ('40S', 'SCH 40S', ScheduleEspessura.Aplicacao.INOX, 170),
    ('80S', 'SCH 80S', ScheduleEspessura.Aplicacao.INOX, 180),
]


class Command(BaseCommand):
    help = 'Popula cadastro mestre de schedules/espessuras (idempotente).'

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for codigo_oficial, descricao, aplicacao, ordem in SCHEDULES_BASE:
            obj, was_created = ScheduleEspessura.objects.get_or_create(
                codigo_schedule=codigo_oficial,
                defaults={
                    'codigo': codigo_oficial,
                    'descricao': descricao,
                    'aplicacao': aplicacao,
                    'ordem': ordem,
                    'ativo': True,
                },
            )
            if was_created:
                created += 1
                continue

            changed = False
            expected = {
                'codigo': codigo_oficial,
                'descricao': descricao,
                'aplicacao': aplicacao,
                'ordem': ordem,
            }
            for field, value in expected.items():
                if getattr(obj, field) != value:
                    setattr(obj, field, value)
                    changed = True
            if not obj.ativo:
                obj.ativo = True
                changed = True
            if changed:
                obj.save(
                    update_fields=['codigo', 'descricao', 'aplicacao', 'ordem', 'ativo'],
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Schedules criados: {created}'))
        self.stdout.write(self.style.SUCCESS(f'Schedules atualizados: {updated}'))
