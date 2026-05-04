# Garante comprimento suficiente para BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS (34 chars).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0003_familia_tipo_regra_rename'),
    ]

    operations = [
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
