"""Sincroniza status fiscal quando NF-e já está AUTORIZADA_HOMOLOGACAO na SEFAZ."""

from django.db import migrations


def sync_status_autorizada_homologacao(apps, schema_editor):
    NFeSaida = apps.get_model('fiscal', 'NFeSaida')
    NFeSaida.objects.filter(
        status_emissao_sefaz='AUTORIZADA_HOMOLOGACAO',
    ).exclude(status='AUTORIZADA_HOMOLOGACAO').update(status='AUTORIZADA_HOMOLOGACAO')


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0032_nfe_homolog_serie_0'),
    ]

    operations = [
        migrations.RunPython(sync_status_autorizada_homologacao, migrations.RunPython.noop),
    ]
