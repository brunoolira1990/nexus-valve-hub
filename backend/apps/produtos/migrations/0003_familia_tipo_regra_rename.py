# Renomeia tipo_regra_codigo e realinha flags com a nova convenção.

from django.db import migrations, models

MAP = {
    'BASE_PP': 'BASE_POLEGADA',
    'BASE_ROSCA_PP': 'BASE_ROSCA_POLEGADA',
    'BASE_DOIS_P': 'BASE_DUAS_POLEGADAS',
    'BASE_ROSCA_DOIS_P': 'BASE_ROSCA_DUAS_POLEGADAS',
    'BASE_SCHED_PP': 'BASE_SCHEDULE_POLEGADA',
    'BASE_SCHED_DOIS_P': 'BASE_SCHEDULE_DUAS_POLEGADAS',
    'BASE_UNDERSCORE_P': 'UNDERSCORE_POLEGADA',
}

FLAGS = {
    'BASE_POLEGADA': (False, False, True, False),
    'BASE_ROSCA_POLEGADA': (True, False, True, False),
    'BASE_DUAS_POLEGADAS': (False, False, True, True),
    'BASE_ROSCA_DUAS_POLEGADAS': (True, False, True, True),
    'BASE_SCHEDULE_POLEGADA': (False, True, True, False),
    'BASE_SCHEDULE_DUAS_POLEGADAS': (False, True, True, True),
    'BASE_ROSCA_SCHEDULE_POLEGADA': (True, True, True, False),
    'BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS': (True, True, True, True),
    'UNDERSCORE_POLEGADA': (False, False, True, False),
    'MANUAL_FABRICANTE': (False, False, False, False),
}


def forwards_regra_e_flags(apps, schema_editor):
    Familia = apps.get_model('produtos', 'FamiliaProduto')
    for row in Familia.objects.all():
        t = row.tipo_regra_codigo
        if t in MAP:
            row.tipo_regra_codigo = MAP[t]
            t = row.tipo_regra_codigo
        if t in FLAGS:
            ur, us, up, us2 = FLAGS[t]
            row.usa_rosca_conexao = ur
            row.usa_schedule = us
            row.usa_polegada_principal = up
            row.usa_polegada_secundaria = us2
        row.save(
            update_fields=[
                'tipo_regra_codigo',
                'usa_rosca_conexao',
                'usa_schedule',
                'usa_polegada_principal',
                'usa_polegada_secundaria',
            ],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0002_familia_rosca_schedule_produto_expand'),
    ]

    operations = [
        migrations.RunPython(forwards_regra_e_flags, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='familiaproduto',
            name='tipo_regra_codigo',
            field=models.CharField(
                choices=[
                    ('BASE_POLEGADA', 'Base + polegada principal'),
                    ('BASE_ROSCA_POLEGADA', 'Base + rosca/conexão + polegada principal'),
                    ('BASE_DUAS_POLEGADAS', 'Base + duas polegadas (IDs)'),
                    ('BASE_ROSCA_DUAS_POLEGADAS', 'Base + rosca + duas polegadas'),
                    ('BASE_SCHEDULE_POLEGADA', 'Base + schedule + polegada principal'),
                    ('BASE_SCHEDULE_DUAS_POLEGADAS', 'Base + schedule + duas polegadas'),
                    ('BASE_ROSCA_SCHEDULE_POLEGADA', 'Base + rosca + schedule + polegada principal'),
                    ('BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS', 'Base + rosca + schedule + duas polegadas'),
                    ('UNDERSCORE_POLEGADA', 'Base + underscore + ID polegada (3 dígitos)'),
                    ('MANUAL_FABRICANTE', 'Manual / fabricante (sem código automático por família)'),
                ],
                default='BASE_POLEGADA',
                max_length=48,
            ),
        ),
    ]
