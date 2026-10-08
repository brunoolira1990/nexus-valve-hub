from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0010_colaborador'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='informacoes_complementares_nfe',
            field=models.TextField(
                blank=True,
                default='',
                help_text=(
                    'Informações recorrentes deste cliente para Dados Adicionais da NF-e/DANFE '
                    '(endereço de entrega, horário de recebimento, instruções externas).'
                ),
            ),
        ),
    ]
