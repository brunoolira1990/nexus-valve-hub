# Generated manually for prazo de entrega, data prevista e totais por item (pedido de compra).

from decimal import Decimal

from django.db import migrations, models


def forwards_backfill_itens(apps, schema_editor):
    Item = apps.get_model('comercial', 'ItemPedidoCompra')
    Pedido = apps.get_model('comercial', 'PedidoCompra')
    for it in Item.objects.all().iterator():
        q = it.quantidade_negociada or it.quantidade or Decimal('0')
        p = it.preco_por_unidade_negociada or it.valor_unitario or Decimal('0')
        vp = (q * p).quantize(Decimal('0.01'))
        it.valor_produtos = vp
        it.valor_total_item = vp
        it.save(update_fields=['valor_produtos', 'valor_total_item'])
    for pe in Pedido.objects.all().iterator():
        tot = sum((it.valor_total_item for it in pe.itens.all()), Decimal('0'))
        pe.valor_total = tot.quantize(Decimal('0.01'))
        pe.save(update_fields=['valor_total'])


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0010_itempedidocompra_snapshot_produto_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidocompra',
            name='prazo_entrega_texto',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='pedidocompra',
            name='data_prevista_entrega',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='ipi_percentual',
            field=models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=7),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='ipi_valor',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='icms_st_percentual',
            field=models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=7),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='icms_st_valor',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='desconto_valor',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='frete_valor',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='outras_despesas_valor',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='valor_produtos',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidocompra',
            name='valor_total_item',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14),
        ),
        migrations.RunPython(forwards_backfill_itens, migrations.RunPython.noop),
    ]
