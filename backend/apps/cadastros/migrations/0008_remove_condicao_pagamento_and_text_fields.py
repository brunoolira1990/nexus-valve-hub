import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0007_alter_condicaopagamento_dias_parcelas"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="cliente",
            name="condicao_pagamento_padrao",
        ),
        migrations.RemoveField(
            model_name="fornecedor",
            name="condicao_pagamento_padrao",
        ),
        migrations.AddField(
            model_name="cliente",
            name="condicao_pagamento_texto",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="cliente",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="quantidade_parcelas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="condicao_pagamento_texto",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="dias_parcelas",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="quantidade_parcelas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.DeleteModel(
            name="CondicaoPagamento",
        ),
    ]
