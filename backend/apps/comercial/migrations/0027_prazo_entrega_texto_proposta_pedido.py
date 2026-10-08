# Comercial 2.6.3 — prazo de entrega textual (proposta e pedido de venda)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0026_vendedor_colaborador_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='prazo_entrega_texto',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='prazo_entrega_texto',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
