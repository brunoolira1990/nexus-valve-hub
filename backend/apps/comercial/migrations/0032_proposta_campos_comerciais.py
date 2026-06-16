from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0031_normalizar_fat_legado'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='validade_dias',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Validade comercial em dias (a partir da data da proposta).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='proposta',
            name='frete_texto',
            field=models.CharField(
                blank=True,
                help_text='Frete / condição de frete comercial (texto livre; não altera NF-e).',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='proposta',
            name='mensagem_comercial',
            field=models.TextField(
                blank=True,
                help_text='Mensagem comercial exibida ao cliente (PDF e proposta).',
            ),
        ),
        migrations.AddField(
            model_name='proposta',
            name='observacoes_proposta',
            field=models.TextField(
                blank=True,
                help_text='Observações gerais da proposta comercial.',
            ),
        ),
        migrations.AddField(
            model_name='proposta',
            name='referencia_cliente',
            field=models.CharField(
                blank=True,
                help_text='Nº da requisição ou cotação do cliente.',
                max_length=128,
            ),
        ),
    ]
