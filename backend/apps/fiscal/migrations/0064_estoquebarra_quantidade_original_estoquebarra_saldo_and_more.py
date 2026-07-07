from decimal import Decimal

from django.db import migrations, models


def backfill_saldo_generico(apps, schema_editor):
    EstoqueBarra = apps.get_model("fiscal", "EstoqueBarra")
    for barra in EstoqueBarra.objects.all().iterator():
        comp = barra.comprimento_original_m
        saldo_m = barra.saldo_m
        barra.tipo_composicao = "BARRA_M"
        barra.unidade_base = barra.unidade_base or "M"
        barra.quantidade_original = comp if comp is not None else Decimal("0")
        barra.saldo = saldo_m if saldo_m is not None else Decimal("0")
        barra.save(update_fields=["tipo_composicao", "unidade_base", "quantidade_original", "saldo"])


class Migration(migrations.Migration):

    dependencies = [
        ("fiscal", "0063_composicao_grupo_barras"),
    ]

    operations = [
        migrations.AddField(
            model_name="estoquebarra",
            name="quantidade_original",
            field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="estoquebarra",
            name="saldo",
            field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="estoquebarra",
            name="tipo_composicao",
            field=models.CharField(choices=[("BARRA_M", "Barra (metros)"), ("PECA_KG", "Pe\u00e7a/chapa (kg)")], default="BARRA_M", max_length=16),
        ),
        migrations.AlterField(
            model_name="estoquebarra",
            name="comprimento_original_m",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True),
        ),
        migrations.AlterField(
            model_name="estoquebarra",
            name="saldo_m",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True),
        ),
        migrations.RunPython(backfill_saldo_generico, migrations.RunPython.noop),
    ]
