from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0012_regrafiscalsaida_recomendacoes_nfe'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrafiscalsaida',
            name='difal_aplicavel',
            field=models.BooleanField(
                blank=True,
                help_text='Calcula DIFAL/ICMSUFDest em venda interestadual a consumidor final não contribuinte.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='regrafiscalsaida',
            name='aliquota_icms_interestadual',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='Alíquota interestadual (pICMSInter) para DIFAL.',
                max_digits=7,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='regrafiscalsaida',
            name='aliquota_icms_interna_destino',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='Alíquota interna da UF destino (pICMSUFDest) para DIFAL.',
                max_digits=7,
                null=True,
            ),
        ),
    ]
