# Data migration: seed SequenciaPedidoCompra a partir de números PC-* e corrigir numeros vazios.

import re
from datetime import datetime

from django.db import IntegrityError, migrations, transaction


def seed_sequencias_e_corrigir_numeros_vazios(apps, schema_editor):
    Pedido = apps.get_model('comercial', 'PedidoCompra')
    Seq = apps.get_model('comercial', 'SequenciaPedidoCompra')
    pat = re.compile(r'^PC-(\d{8})-(\d{4})$')
    by_date = {}
    for p in Pedido.objects.exclude(numero='').iterator():
        m = pat.match((p.numero or '').strip())
        if not m:
            continue
        d = datetime.strptime(m.group(1), '%Y%m%d').date()
        n = int(m.group(2))
        by_date[d] = max(by_date.get(d, 0), n)
    for d, mx in by_date.items():
        Seq.objects.update_or_create(
            data_referencia=d,
            defaults={'proximo_numero': mx + 1},
        )

    for p in Pedido.objects.filter(numero='').order_by('id'):
        with transaction.atomic():
            s = Seq.objects.select_for_update().filter(data_referencia=p.data).first()
            if s is None:
                try:
                    Seq.objects.create(data_referencia=p.data, proximo_numero=1)
                except IntegrityError:
                    pass
                s = Seq.objects.select_for_update().get(data_referencia=p.data)
            n = s.proximo_numero
            s.proximo_numero = n + 1
            s.save(update_fields=['proximo_numero'])
            suffix = p.data.strftime('%Y%m%d')
            Pedido.objects.filter(pk=p.pk).update(numero=f'PC-{suffix}-{n:04d}')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0012_sequencia_pedido_compra'),
    ]

    operations = [
        migrations.RunPython(seed_sequencias_e_corrigir_numeros_vazios, noop_reverse),
    ]
