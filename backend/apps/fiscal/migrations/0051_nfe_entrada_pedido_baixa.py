from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0050_xml_conteudo_nfe_cte_importados'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='pedido_baixa_aplicado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='pedido_baixa_aplicado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='conferencias_pedido_baixa_aplicado',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='pedido_baixa_aplicada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='quantidade_pedido_baixada',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
    ]
