from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("comercial", "0003_itemproposta_price_composition_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="proposta",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="propostas",
                to="cadastros.cliente",
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="cliente_avulso_nome",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="itemproposta",
            name="produto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="produtos.produto",
            ),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="descricao_avulsa",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RemoveField(
            model_name="itemproposta",
            name="impostos_no_custo",
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="ipi_custo",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="st_custo",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="outros_impostos_custo",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14),
        ),
    ]
