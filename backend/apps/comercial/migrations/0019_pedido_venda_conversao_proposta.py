from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0018_rename_comercial_h_proposta_criado_idx_comercial_h_propost_41171e_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidovenda',
            name='observacoes_comerciais',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='observacoes_internas',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='prazo_entrega',
            field=models.DateField(
                blank=True,
                help_text='Prazo de entrega previsto (ex.: validade da proposta).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='snapshot_conversao',
            field=models.JSONField(
                blank=True,
                help_text='Snapshot comercial/fiscal no momento da conversão.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='vendedor',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='itempedidovenda',
            name='desconto',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='itempedidovenda',
            name='item_proposta',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='itens_pedido_venda',
                to='comercial.itemproposta',
            ),
        ),
        migrations.AddField(
            model_name='itempedidovenda',
            name='snapshot_fiscal',
            field=models.JSONField(
                blank=True,
                help_text='Impostos/origem fiscal herdados da proposta na conversão.',
                null=True,
            ),
        ),
    ]
