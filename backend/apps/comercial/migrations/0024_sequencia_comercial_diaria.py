# Comercial 2.2.1 — sequência comercial por dia (padrão PC-AAAAMMDD-NNNN)

from django.db import migrations, models


def migrar_sequencias_globais_para_diarias(apps, schema_editor):
    from apps.comercial.numbering import (
        TIPO_PEDIDO_VENDA,
        TIPO_PROPOSTA,
        extrair_sequencial_diario,
    )

    Seq = apps.get_model('comercial', 'SequenciaComercial')
    Proposta = apps.get_model('comercial', 'Proposta')
    PedidoVenda = apps.get_model('comercial', 'PedidoVenda')

    Seq.objects.all().delete()

    def seed_tipo(tipo, prefix, queryset):
        por_dia: dict = {}
        for numero in queryset.values_list('numero', flat=True):
            par = extrair_sequencial_diario(numero or '', prefix)
            if par is None:
                continue
            data_ref, seq = par
            por_dia[data_ref] = max(por_dia.get(data_ref, 0), seq)
        for data_ref, max_seq in por_dia.items():
            Seq.objects.update_or_create(
                tipo=tipo,
                data_referencia=data_ref,
                defaults={'proximo_numero': max_seq + 1},
            )

    seed_tipo(TIPO_PROPOSTA, 'PROP', Proposta.objects.all())
    seed_tipo(TIPO_PEDIDO_VENDA, 'PV', PedidoVenda.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0023_reseed_sequencia_comercial_cq_style'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sequenciacomercial',
            name='tipo',
            field=models.CharField(
                choices=[('PROPOSTA', 'Proposta'), ('PEDIDO_VENDA', 'Pedido de venda')],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='sequenciacomercial',
            name='data_referencia',
            field=models.DateField(db_index=True, null=True),
        ),
        migrations.RunPython(migrar_sequencias_globais_para_diarias, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='sequenciacomercial',
            name='data_referencia',
            field=models.DateField(db_index=True),
        ),
        migrations.AddConstraint(
            model_name='sequenciacomercial',
            constraint=models.UniqueConstraint(
                fields=('tipo', 'data_referencia'),
                name='comercial_sequenciacomercial_tipo_data_uniq',
            ),
        ),
        migrations.AlterModelOptions(
            name='sequenciacomercial',
            options={
                'ordering': ['-data_referencia', 'tipo'],
                'verbose_name': 'Sequência comercial',
                'verbose_name_plural': 'Sequências comerciais',
            },
        ),
    ]
