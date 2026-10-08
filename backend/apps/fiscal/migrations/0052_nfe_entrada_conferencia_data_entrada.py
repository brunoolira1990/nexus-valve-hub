from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0051_nfe_entrada_pedido_baixa'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='data_entrada',
            field=models.DateField(
                blank=True,
                help_text='Data operacional/fiscal de entrada informada pelo usuário na finalização.',
                null=True,
            ),
        ),
    ]
