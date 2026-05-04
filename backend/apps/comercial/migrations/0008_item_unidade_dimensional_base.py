from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comercial", "0007_itemproposta_ncm_avulso"),
    ]

    operations = []

    for model_name in ("itemproposta", "itempedidovenda", "itempedidocompra"):
        operations.extend(
            [
                migrations.AddField(
                    model_name=model_name,
                    name="barras_total",
                    field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="fator_conversao",
                    field=models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="metros_total",
                    field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="peso_total_kg",
                    field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="preco_por_kg",
                    field=models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="preco_por_metro",
                    field=models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="preco_por_unidade_negociada",
                    field=models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="quantidade_estoque_calculada",
                    field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="quantidade_negociada",
                    field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="unidade_estoque_calculada",
                    field=models.CharField(blank=True, max_length=16),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name="unidade_negociada",
                    field=models.CharField(blank=True, max_length=16),
                ),
            ]
        )
