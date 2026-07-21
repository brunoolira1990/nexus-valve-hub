from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0065_itemnfesaida_valor_preco_unitario_4_casas'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NFeEntradaConferenciaReaberturaEvento',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'tipo_operacao',
                    models.CharField(
                        default='REABERTURA_ENTRADA_FORNECEDOR',
                        editable=False,
                        max_length=48,
                    ),
                ),
                ('motivo', models.TextField()),
                ('estado_anterior', models.CharField(max_length=16)),
                ('estado_posterior', models.CharField(max_length=16)),
                ('resumo_tecnico', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'conferencia',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='eventos_reabertura',
                        to='fiscal.nfeentradaconferencia',
                    ),
                ),
                (
                    'usuario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='reaberturas_conferencia_nfe_entrada',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-criado_em', '-id'],
                'indexes': [
                    models.Index(
                        fields=['conferencia', 'criado_em'],
                        name='fiscal_reab_conf_criado_idx',
                    ),
                ],
            },
        ),
    ]
