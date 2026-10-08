# Espigão x Flange: tipo dimensional + regra de código E…F…

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0018_produto_dim_aba_mm_produto_dim_aba_polegada_ref_and_more'),
    ]

    operations = [
        migrations.AlterField(
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
                    ('OD_MM_X_ESPESSURA_X_COMPRIMENTO', 'OD mm + espessura + comprimento'),
                    ('CHAPA_MM', 'Chapa em mm (espessura x largura x comprimento)'),
                    ('CHAPA_FURO_MM', 'Chapa com furo em mm (furo x espessura x largura x comprimento)'),
                    ('BARRA_CHATA_MM', 'Barra chata em mm (largura x espessura [x comprimento])'),
                    ('METALON_MM', 'Metalon em mm (altura x largura x espessura)'),
                    ('CANTONEIRA_MM', 'Cantoneira em mm (aba x espessura [x comprimento])'),
                    ('CANTONEIRA_POLEGADA', 'Cantoneira em polegada (aba x espessura)'),
                    ('PERFIL_RETANGULAR_MM', 'Perfil retangular em mm (altura x largura x espessura)'),
                    ('DIMENSIONAL_LIVRE_CONTROLADO', 'Dimensional livre controlado'),
                    ('FLANGE', 'Flange (orientação)'),
                    ('ESPIGAO_X_FLANGE', 'Espigão x Flange (duas NPS + texto flange na base)'),
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
                    ('BASE_OD_MM_ESPESSURA', 'Base + OD mm + espessura mm (ex.: 6119OD.1002)'),
                    ('BASE_ESPIGAO_FLANGE_NPS', 'Base + espigão NPS + flange NPS — {fig}.E{id}F{id}'),
                    ('MANUAL_FABRICANTE', 'Manual / fabricante (sem código automático por família)'),
                ],
                default='BASE_POLEGADA',
                max_length=48,
            ),
        ),
    ]
