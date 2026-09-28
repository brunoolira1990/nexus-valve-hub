from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0043_cotacao_componentes_custo'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidovenda',
            name='desconto_cabecalho_tipo',
            field=models.CharField(
                choices=[('valor', 'R$'), ('percentual', '%')],
                default='valor',
                help_text='Tipo do desconto do cabeçalho: valor em R$ ou percentual (%).',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='desconto_cabecalho',
            field=models.DecimalField(
                blank=True,
                default=Decimal('0'),
                decimal_places=2,
                help_text='Desconto aplicado no total do pedido (R$ ou % conforme desconto_cabecalho_tipo).',
                max_digits=14,
                null=True,
            ),
        ),
    ]
