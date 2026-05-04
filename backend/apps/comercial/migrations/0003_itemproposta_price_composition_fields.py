from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comercial", "0002_payment_condition_snapshot_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemproposta",
            name="custo_utilizado",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="frete",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="despesas",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="impostos_no_custo",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="custo_final",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="modo_preco",
            field=models.CharField(default="sugerido", max_length=16),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="preco_sugerido",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="preco_final",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="margem_resultante",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=8),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="lucro_resultante",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
    ]
