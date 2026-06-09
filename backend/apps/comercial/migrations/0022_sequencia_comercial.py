# Generated manually — Comercial 2.2

from django.db import migrations, models


def seed_sequencias(apps, schema_editor):
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

    Seq.objects.get_or_create(tipo=TIPO_PROPOSTA, defaults={'proximo_numero': max_prop + 1})
    Seq.objects.get_or_create(tipo=TIPO_PEDIDO_VENDA, defaults={'proximo_numero': max_pv + 1})


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0021_faturamentopedidovenda_nfe_saida_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SequenciaComercial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('PROPOSTA', 'Proposta'), ('PEDIDO_VENDA', 'Pedido de venda')], max_length=32, unique=True)),
                ('proximo_numero', models.PositiveIntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Sequência comercial',
                'verbose_name_plural': 'Sequências comerciais',
            },
        ),
        migrations.RunPython(seed_sequencias, migrations.RunPython.noop),
    ]
