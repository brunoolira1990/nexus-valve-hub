# CondicaoPagamento: parcelas/dias_entre_parcelas -> dias_parcelas (ArrayField)

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0004_condicao_pagamento_e_campos_cadastros"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="condicaopagamento",
            name="parcelas",
        ),
        migrations.RemoveField(
            model_name="condicaopagamento",
            name="dias_entre_parcelas",
        ),
        migrations.AddField(
            model_name="condicaopagamento",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="condicaopagamento",
            name="descricao",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
