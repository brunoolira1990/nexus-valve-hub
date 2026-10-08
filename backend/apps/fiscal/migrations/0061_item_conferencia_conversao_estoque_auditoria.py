from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0060_item_nfe_entrada_conferencia_equivalencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='conversao_estoque_auditoria',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
