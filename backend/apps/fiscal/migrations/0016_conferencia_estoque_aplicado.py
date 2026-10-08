import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('corridas', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0015_atendimento_estoque_linha'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='estoque_aplicado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='estoque_aplicado_observacao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='estoque_aplicado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='conferencias_estoque_aplicado',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='estoque_aplicado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='quantidade_estoque_aplicada',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='corrida_estoque',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='itens_conferencia_entrada',
                to='corridas.corrida',
            ),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='estoque_corrida',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='itens_conferencia_entrada',
                to='fiscal.estoquecorrida',
            ),
        ),
    ]
