from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0045_pedidocompra_desconto_cabecalho_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='itempedidocompra',
            name='desconto_tipo',
            field=models.CharField(
                choices=[('valor', 'R$'), ('percentual', '%')],
                default='valor',
                help_text='Tipo do desconto do item: valor em R$ ou percentual (%).',
                max_length=12,
            ),
        ),
    ]
