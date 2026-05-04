from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("produtos", "0006_dimensional_conversion_base"),
    ]

    operations = [
        migrations.AddField(
            model_name="produto",
            name="observacoes_conversao",
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name="produto",
            name="unidades_compra_permitidas",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
