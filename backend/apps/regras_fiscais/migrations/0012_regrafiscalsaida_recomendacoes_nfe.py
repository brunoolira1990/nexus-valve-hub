from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0011_regrafiscalsaida_deduzir_icms_base_pis_cofins'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrafiscalsaida',
            name='recomendacoes_nfe',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
