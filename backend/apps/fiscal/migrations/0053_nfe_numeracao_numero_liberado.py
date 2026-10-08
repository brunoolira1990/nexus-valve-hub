import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0052_nfe_entrada_conferencia_data_entrada'),
    ]

    operations = [
        migrations.CreateModel(
            name='NFeNumeracaoNumeroLiberado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveIntegerField()),
                ('liberado_em', models.DateTimeField(auto_now_add=True)),
                ('motivo', models.TextField(blank=True)),
                ('consumido_em', models.DateTimeField(blank=True, null=True)),
                (
                    'configuracao',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='numeros_liberados',
                        to='fiscal.nfenumeracaoconfiguracao',
                    ),
                ),
                (
                    'liberado_por',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='numeros_nfe_liberados',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'nfe_saida_consumo',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='numeracao_reutilizada_de',
                        to='fiscal.nfesaida',
                    ),
                ),
                (
                    'nfe_saida_origem',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='numeracao_liberada_origem',
                        to='fiscal.nfesaida',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Número NF-e liberado para reutilização',
                'verbose_name_plural': 'Números NF-e liberados para reutilização',
                'ordering': ['configuracao_id', 'numero'],
            },
        ),
        migrations.AddIndex(
            model_name='nfenumeracaonumeroliberado',
            index=models.Index(fields=['configuracao', 'consumido_em', 'numero'], name='fiscal_nfe__configu_8a1f2d_idx'),
        ),
        migrations.AddConstraint(
            model_name='nfenumeracaonumeroliberado',
            constraint=models.UniqueConstraint(
                condition=models.Q(('consumido_em__isnull', True)),
                fields=('configuracao', 'numero'),
                name='uniq_nfe_numero_liberado_disponivel',
            ),
        ),
    ]
