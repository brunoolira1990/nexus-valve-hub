# Generated manually for tipo_dimensional, regra 11 (BASE_OD_MM_ESPESSURA) e campos mm no produto.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0012_popular_codigo_oficial_polegada'),
    ]

    operations = [
        migrations.AddField(
            model_name='familiaproduto',
            name='tipo_dimensional',
            field=models.CharField(
                choices=[
                    ('SIMPLES', 'Simples (somente regra de código)'),
                    ('NPS', 'NPS — polegada nominal'),
                    ('NPS_SCHEDULE', 'NPS + Schedule (SCH)'),
                    ('REDUCAO_NPS', 'Redução NPS + Schedule'),
                    ('ROSCA', 'Rosca / conexão (orientação)'),
                    ('ROSCA_X_ROSCA', 'Rosca x Rosca (orientação)'),
                    ('NPS_X_ROSCA', 'NPS x Rosca'),
                    ('OD_POLEGADA', 'OD em polegada (não é NPS/SCH)'),
                    ('OD_POLEGADA_X_ROSCA', 'OD em polegada x Rosca'),
                    ('OD_MM', 'OD em mm (tubo / dimensional)'),
                    ('OD_MM_X_ESPESSURA', 'OD mm + espessura mm'),
                    (
                        'OD_MM_X_ESPESSURA_X_COMPRIMENTO',
                        'OD mm + espessura + comprimento',
                    ),
                    ('FLANGE', 'Flange (orientação)'),
                    ('VALVULA', 'Válvula (orientação)'),
                    ('MANUAL', 'Dimensional manual / sem padrão automático'),
                    ('LEGADO', 'Legado / misto (orientação)'),
                ],
                default='SIMPLES',
                help_text='Significado dimensional dos campos (rótulos, obrigatoriedade, descrição). '
                'A montagem do código continua definida apenas por tipo_regra_codigo.',
                max_length=48,
            ),
        ),
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
                    (
                        'BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS',
                        'Base + rosca + schedule + duas polegadas',
                    ),
                    ('UNDERSCORE_POLEGADA', 'Base + underscore + ID polegada (3 dígitos)'),
                    (
                        'BASE_OD_MM_ESPESSURA',
                        'Base + OD mm + espessura mm (ex.: 6119OD.1002)',
                    ),
                    (
                        'MANUAL_FABRICANTE',
                        'Manual / fabricante (sem código automático por família)',
                    ),
                ],
                default='BASE_POLEGADA',
                max_length=48,
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='od_mm',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text='OD externo em mm (tubo / dimensional; não confundir com NPS).',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='espessura_mm',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='comprimento_mm',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=14,
                null=True,
            ),
        ),
    ]
