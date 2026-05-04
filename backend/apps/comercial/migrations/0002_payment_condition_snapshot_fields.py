import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comercial", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedidocompra",
            name="condicao_pagamento_texto",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="pedidocompra",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="pedidocompra",
            name="quantidade_parcelas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="pedidocompra",
            name="vencimentos_previstos",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.DateField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="pedidovenda",
            name="condicao_pagamento_texto",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="pedidovenda",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="pedidovenda",
            name="quantidade_parcelas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="pedidovenda",
            name="vencimentos_previstos",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.DateField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="condicao_pagamento_texto",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="proposta",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="quantidade_parcelas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="proposta",
            name="vencimentos_previstos",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.DateField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
    ]
