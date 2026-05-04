from django.db import migrations, models
import django.db.models.deletion


def forwards_empresa_emitente(apps, schema_editor):
    Empresa = apps.get_model('cadastros', 'Empresa')
    Proposta = apps.get_model('comercial', 'Proposta')
    PedidoVenda = apps.get_model('comercial', 'PedidoVenda')
    first = Empresa.objects.order_by('pk').first()
    if first:
        Proposta.objects.filter(empresa_emitente__isnull=True).update(empresa_emitente_id=first.pk)
        PedidoVenda.objects.filter(empresa_emitente__isnull=True).update(empresa_emitente_id=first.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0009_alter_cliente_dias_parcelas_and_more'),
        ('comercial', '0005_proposta_fiscal_context_item_pricing'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='empresa_emitente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='propostas_emitidas',
                to='cadastros.empresa',
            ),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='empresa_emitente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='pedidos_venda_emitidos',
                to='cadastros.empresa',
            ),
        ),
        migrations.RunPython(forwards_empresa_emitente, migrations.RunPython.noop),
    ]
