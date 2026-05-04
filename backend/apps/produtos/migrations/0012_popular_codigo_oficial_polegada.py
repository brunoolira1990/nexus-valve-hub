from decimal import Decimal

from django.db import migrations


def _parse_decimal(descricao: str):
    txt = (descricao or '').replace('"', '').strip().replace('-', '.').replace(' ', '.')
    if not txt:
        return None
    parts = [p for p in txt.split('.') if p]
    try:
        if len(parts) == 1:
            if '/' in parts[0]:
                n, d = parts[0].split('/', 1)
                return Decimal(n) / Decimal(d)
            return Decimal(parts[0])
        if len(parts) == 2 and '/' in parts[1]:
            n, d = parts[1].split('/', 1)
            return Decimal(parts[0]) + (Decimal(n) / Decimal(d))
    except Exception:  # noqa: BLE001
        return None
    return None


def popular_polegada(apps, schema_editor):
    Polegada = apps.get_model('produtos', 'Polegada')
    for row in Polegada.objects.all():
        changed = []
        if not row.codigo_oficial:
            row.codigo_oficial = row.codigo
            changed.append('codigo_oficial')
        if row.valor_decimal is None:
            dec = _parse_decimal(row.descricao)
            if dec is not None:
                row.valor_decimal = dec
                row.valor_mm = (dec * Decimal('25.4')).quantize(Decimal('0.001'))
                changed.extend(['valor_decimal', 'valor_mm'])
        if changed:
            row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ('produtos', '0011_alter_polegada_options_polegada_aliases_and_more'),
    ]

    operations = [
        migrations.RunPython(popular_polegada, migrations.RunPython.noop),
    ]
