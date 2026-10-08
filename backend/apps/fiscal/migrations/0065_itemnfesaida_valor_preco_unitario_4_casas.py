from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Amplia ItemNFeSaida.valor de numeric(14,2) para numeric(16,4).

    - decimal_places=4: alinhamento técnico com ItemFaturamentoPedidoVenda.valor_unitario
    - max_digits=16: preserva 12 dígitos inteiros de numeric(14,2) (14-2=12 → 16-4=12)
    - Validação de aplicação continua limitando a 3 casas significativas
    - Valores históricos existentes não são recalculados
    """

    dependencies = [
        ('fiscal', '0064_estoquebarra_quantidade_original_estoquebarra_saldo_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itemnfesaida',
            name='valor',
            field=models.DecimalField(decimal_places=4, max_digits=16),
        ),
    ]
