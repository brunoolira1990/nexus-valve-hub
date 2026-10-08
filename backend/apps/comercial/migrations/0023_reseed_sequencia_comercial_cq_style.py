# Comercial 2.2.1 — reseed sequências com padrão PROP{n}/PV{n} e legado PROP-…/PV-…

from django.db import migrations


def reseed_sequencias(apps, schema_editor):
    from apps.comercial.numbering import (
        TIPO_PEDIDO_VENDA,
        TIPO_PROPOSTA,
        extrair_sequencial_pedido_venda,
        extrair_sequencial_proposta,
    )

    Seq = apps.get_model('comercial', 'SequenciaComercial')
    Proposta = apps.get_model('comercial', 'Proposta')
    PedidoVenda = apps.get_model('comercial', 'PedidoVenda')

    max_prop = 0
    for numero in Proposta.objects.values_list('numero', flat=True):
        n = extrair_sequencial_proposta(numero or '')
        if n is not None:
            max_prop = max(max_prop, n)

    max_pv = 0
    for numero in PedidoVenda.objects.values_list('numero', flat=True):
        n = extrair_sequencial_pedido_venda(numero or '')
        if n is not None:
            max_pv = max(max_pv, n)

    seq_prop, _ = Seq.objects.get_or_create(tipo=TIPO_PROPOSTA, defaults={'proximo_numero': 1})
    seq_pv, _ = Seq.objects.get_or_create(tipo=TIPO_PEDIDO_VENDA, defaults={'proximo_numero': 1})
    if seq_prop.proximo_numero < max_prop + 1:
        seq_prop.proximo_numero = max_prop + 1
        seq_prop.save(update_fields=['proximo_numero'])
    if seq_pv.proximo_numero < max_pv + 1:
        seq_pv.proximo_numero = max_pv + 1
        seq_pv.save(update_fields=['proximo_numero'])


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0022_sequencia_comercial'),
    ]

    operations = [
        migrations.RunPython(reseed_sequencias, migrations.RunPython.noop),
    ]
