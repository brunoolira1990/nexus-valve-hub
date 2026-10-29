from django.db import migrations

from apps.regras_fiscais.aliquotas_uf_seed import ALICOTAS_ICMS_UF


def popular_aliquotas_uf(apps, schema_editor):
    AliquotaIcmsUF = apps.get_model('regras_fiscais', 'AliquotaIcmsUF')
    rows = [
        AliquotaIcmsUF(
            uf=uf,
            alias='',
            aliquota_interna=str(dados['interna']),
            aliquota_interestadual=str(dados['interestadual']),
            aliquota_fcp=str(dados['fcp']) if dados['fcp'] is not None else None,
            ativo=True,
        )
        for uf, dados in ALICOTAS_ICMS_UF.items()
    ]
    AliquotaIcmsUF.objects.bulk_create(rows)


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0015_aliquotaicmsuf'),
    ]

    operations = [
        migrations.RunPython(popular_aliquotas_uf, migrations.RunPython.noop),
    ]
