from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0013_seed_sequencia_pedido_compra'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidocompra',
            name='observacoes',
            field=models.TextField(blank=True),
        ),
    ]
