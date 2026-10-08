"""Comercial 2.6.4 — propostas com pedido de venda devem ter status CONVERTIDA."""

from django.db import migrations

from apps.comercial.commercial_defaults import STATUS_PROPOSTA_CONVERTIDA


def sincronizar_status_convertida(apps, schema_editor):
    Proposta = apps.get_model('comercial', 'Proposta')
    PedidoVenda = apps.get_model('comercial', 'PedidoVenda')
    proposta_ids = (
        PedidoVenda.objects.exclude(proposta_id__isnull=True)
        .values_list('proposta_id', flat=True)
        .distinct()
    )
    Proposta.objects.filter(pk__in=proposta_ids).exclude(status=STATUS_PROPOSTA_CONVERTIDA).update(
        status=STATUS_PROPOSTA_CONVERTIDA,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('comercial', '0028_oinput'),
    ]

    operations = [
        migrations.RunPython(sincronizar_status_convertida, migrations.RunPython.noop),
    ]
