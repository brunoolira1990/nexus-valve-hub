from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0082_nfesaida_difal_confirmado_em_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='chegada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='recebido_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='local_recebimento',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='observacao_chegada',
            field=models.TextField(blank=True, default=''),
        ),
    ]
