from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fiscal', '0037_nfe_ciclo_vida_pre_autorizacao_401368'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='ind_final',
            field=models.CharField(
                default='1',
                help_text='Indicador consumidor final (0=Não, 1=Sim).',
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='ind_pres',
            field=models.CharField(
                default='1',
                help_text='Indicador de presença do comprador (tabela NF-e).',
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='indicadores_fiscais_confirmados',
            field=models.BooleanField(
                default=False,
                help_text='Usuário confirmou indFinal e indPres na conferência.',
            ),
        ),
    ]
