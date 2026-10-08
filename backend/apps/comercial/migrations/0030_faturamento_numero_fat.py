"""Numeração própria FAT-YYYYMMDD-NNNN para faturamento de pedido."""

from django.db import migrations, models


def preencher_numero_faturamento_legado(apps, schema_editor):
    Fat = apps.get_model('comercial', 'FaturamentoPedidoVenda')
    for fat in Fat.objects.filter(numero_faturamento=''):
        dt = fat.criado_em.date() if fat.criado_em else None
        if dt:
            fat.numero_faturamento = f'FAT-LEGADO-{dt.strftime("%Y%m%d")}-{fat.pk:04d}'
        else:
            fat.numero_faturamento = f'FAT-LEGADO-{fat.pk:04d}'
        fat.save(update_fields=['numero_faturamento'])


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0029_sync_proposta_status_convertida'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sequenciacomercial',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('PROPOSTA', 'Proposta'),
                    ('PEDIDO_VENDA', 'Pedido de venda'),
                    ('FATURAMENTO', 'Faturamento'),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='faturamentopedidovenda',
            name='numero_faturamento',
            field=models.CharField(blank=True, db_index=True, max_length=32),
        ),
        migrations.RunPython(preencher_numero_faturamento_legado, migrations.RunPython.noop),
    ]
