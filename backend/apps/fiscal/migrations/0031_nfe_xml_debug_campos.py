# Generated manually for NF-e schema XML debug fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0030_nfe_sefaz_lote_protocolo'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='xml_nfe_gerado',
            field=models.TextField(
                blank=True,
                help_text='XML NF-e antes da assinatura (emissão oficial).',
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_envio_lote',
            field=models.TextField(
                blank=True,
                help_text='XML enviNFe enviado à SEFAZ.',
            ),
        ),
    ]
