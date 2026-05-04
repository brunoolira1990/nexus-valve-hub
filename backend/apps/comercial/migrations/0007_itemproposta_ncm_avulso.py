from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0006_proposta_pedido_empresa_emitente'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemproposta',
            name='ncm_avulso',
            field=models.CharField(
                blank=True,
                help_text='NCM informado manualmente quando o item não possui produto cadastrado (regra fiscal).',
                max_length=16,
            ),
        ),
    ]
