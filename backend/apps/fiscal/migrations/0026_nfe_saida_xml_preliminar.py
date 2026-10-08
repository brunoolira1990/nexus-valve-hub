# Generated manually — XML NF-e 4.00 preliminar (sem autorização SEFAZ)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0025_nfe_sefaz_status_diagnostico_361'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='xml_preliminar',
            field=models.TextField(
                blank=True,
                help_text='XML NF-e 4.00 preliminar (conferência). Não é XML autorizado/assinado.',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_preliminar_gerado_em',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Quando o XML preliminar foi gerado pela última vez.',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='chave_acesso_preliminar',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=44,
                help_text='Chave de acesso calculada do XML preliminar (sem protocolo SEFAZ).',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='serie_fiscal_preliminar',
            field=models.CharField(
                blank=True,
                max_length=3,
                help_text='Série fiscal usada no XML preliminar (homologação).',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='numero_fiscal_preliminar',
            field=models.CharField(
                blank=True,
                max_length=9,
                help_text='nNF numérico do XML preliminar (não confundir com número interno ERP).',
            ),
        ),
    ]
