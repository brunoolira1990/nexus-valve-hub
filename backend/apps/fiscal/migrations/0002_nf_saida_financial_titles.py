import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fiscal", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="nfesaida",
            name="condicao_pagamento_texto",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="nfesaida",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="nfesaida",
            name="quantidade_parcelas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="nfesaida",
            name="titulos_receber",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="nfesaida",
            name="vencimentos_finais",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.DateField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
    ]
