"""Normaliza FAT-LEGADO-* para FAT-YYYYMMDD-NNNN no banco."""

import re

from django.db import migrations

_RE_FAT_LEGADO = re.compile(r'^FAT-LEGADO-(\d{8})-(\d+)$', re.I)


def normalizar_fat_legado(apps, schema_editor):
    Fat = apps.get_model('comercial', 'FaturamentoPedidoVenda')
    usados = {
        (n or '').strip()
        for n in Fat.objects.exclude(numero_faturamento='').values_list('numero_faturamento', flat=True)
        if (n or '').strip()
    }
    for fat in Fat.objects.filter(numero_faturamento__startswith='FAT-LEGADO'):
        atual = (fat.numero_faturamento or '').strip()
        m = _RE_FAT_LEGADO.match(atual)
        if not m:
            continue
        data_key = m.group(1)
        seq = int(m.group(2))
        candidato = f'FAT-{data_key}-{seq:04d}'
        while candidato in usados and candidato != atual:
            seq += 1
            candidato = f'FAT-{data_key}-{seq:04d}'
        if candidato != atual:
            fat.numero_faturamento = candidato
            fat.save(update_fields=['numero_faturamento'])
            usados.discard(atual)
            usados.add(candidato)


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0030_faturamento_numero_fat'),
    ]

    operations = [
        migrations.RunPython(normalizar_fat_legado, migrations.RunPython.noop),
    ]
