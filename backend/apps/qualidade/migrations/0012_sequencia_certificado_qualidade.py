import re
from datetime import date

from django.db import migrations, models


def seed_sequencia_certificado_qualidade(apps, schema_editor):
    CertificadoQualidade = apps.get_model('qualidade', 'CertificadoQualidade')
    Sequencia = apps.get_model('qualidade', 'SequenciaCertificadoQualidade')
    re_compacto = re.compile(r'^CQ(\d{8})(\d{4})$', re.I)
    by_date: dict[date, int] = {}
    for cert in CertificadoQualidade.objects.exclude(numero='').iterator():
        bruto = (cert.numero or '').strip().upper().replace(' ', '').replace('-', '')
        while bruto.startswith('CQCQ'):
            bruto = bruto[2:]
        if not bruto.startswith('CQ'):
            bruto = f'CQ{bruto}'
        m = re_compacto.match(bruto)
        if not m:
            continue
        try:
            data_ref = date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
            sequencial = int(m.group(2))
        except ValueError:
            continue
        by_date[data_ref] = max(by_date.get(data_ref, 0), sequencial + 1)
    for data_ref, proximo in by_date.items():
        Sequencia.objects.update_or_create(
            data_referencia=data_ref,
            defaults={'proximo_numero': proximo},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0011_item_cf_rastreabilidade_conferencia'),
    ]

    operations = [
        migrations.CreateModel(
            name='SequenciaCertificadoQualidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_referencia', models.DateField(db_index=True, unique=True)),
                ('proximo_numero', models.PositiveIntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Sequência certificado de qualidade',
                'verbose_name_plural': 'Sequências certificado de qualidade',
                'ordering': ['-data_referencia'],
            },
        ),
        migrations.RunPython(seed_sequencia_certificado_qualidade, migrations.RunPython.noop),
    ]
