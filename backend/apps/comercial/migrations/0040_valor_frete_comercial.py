from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0039_protesto_manual_analise_financeira'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='valor_frete',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                help_text='Valor de frete cobrado do cliente no cabeçalho da proposta.',
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='valor_frete',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                help_text='Valor de frete cobrado do cliente no cabeçalho do pedido.',
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name='faturamentopedidovenda',
            name='valor_frete',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                help_text='Parcela do frete do pedido congelada neste faturamento.',
                max_digits=14,
            ),
        ),
        migrations.AddConstraint(
            model_name='proposta',
            constraint=models.CheckConstraint(
                condition=models.Q(('valor_frete__gte', Decimal('0'))),
                name='prop_valor_frete_nao_negativo',
            ),
        ),
        migrations.AddConstraint(
            model_name='pedidovenda',
            constraint=models.CheckConstraint(
                condition=models.Q(('valor_frete__gte', Decimal('0'))),
                name='pedv_valor_frete_nao_negativo',
            ),
        ),
        migrations.AddConstraint(
            model_name='faturamentopedidovenda',
            constraint=models.CheckConstraint(
                condition=models.Q(('valor_frete__gte', Decimal('0'))),
                name='fatpv_valor_frete_nao_negativo',
            ),
        ),
    ]
