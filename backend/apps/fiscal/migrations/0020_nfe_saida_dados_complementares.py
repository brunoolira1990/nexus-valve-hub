from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0019_rename_nfesaidaevento_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='transportadora',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_saidas',
                to='cadastros.transportadora',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='modalidade_frete',
            field=models.CharField(
                blank=True,
                default='9',
                help_text='Modalidade do frete (9=sem frete, 0=CIF, 1=FOB, etc.).',
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='valor_frete',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='quantidade_volumes',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='peso_bruto',
            field=models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='peso_liquido',
            field=models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='observacoes_nfe',
            field=models.TextField(
                blank=True,
                help_text='Observações complementares da NF-e (editáveis em rascunho).',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='informacoes_adicionais',
            field=models.TextField(
                blank=True,
                help_text='Informações adicionais de interesse do fisco/contribuinte.',
            ),
        ),
    ]
