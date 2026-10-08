from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0034_alter_propostacomercialhistorico_tipo_evento'),
    ]

    operations = [
        migrations.AddField(
            model_name='itempedidocompra',
            name='quantidade_recebida',
            field=models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14),
        ),
    ]
