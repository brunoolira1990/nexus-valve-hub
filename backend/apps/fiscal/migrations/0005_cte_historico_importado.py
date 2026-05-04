import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0004_nfe_hist_eventos_cancelamento'),
    ]

    operations = [
        migrations.CreateModel(
            name='CTeHistoricoImportado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chave_acesso', models.CharField(db_index=True, max_length=44, unique=True)),
                ('numero', models.CharField(max_length=16)),
                ('serie', models.CharField(blank=True, max_length=4)),
                ('modelo', models.CharField(blank=True, max_length=4)),
                ('dh_emissao', models.DateTimeField()),
                ('tp_amb', models.CharField(blank=True, max_length=1)),
                ('nat_op', models.CharField(blank=True, max_length=120)),
                ('cfop', models.CharField(blank=True, max_length=8)),
                ('versao_layout', models.CharField(blank=True, max_length=16)),
                ('cstat', models.CharField(blank=True, max_length=8)),
                ('xmotivo', models.CharField(blank=True, max_length=255)),
                ('protocolo', models.CharField(blank=True, max_length=30)),
                ('cancelado', models.BooleanField(default=False)),
                ('status_documento', models.CharField(default='autorizado', max_length=32)),
                ('data_cancelamento', models.DateTimeField(blank=True, null=True)),
                ('protocolo_cancelamento', models.CharField(blank=True, max_length=30)),
                ('motivo_cancelamento', models.CharField(blank=True, max_length=255)),
                ('valor_total_servico', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('valor_receber', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('componentes_frete_json', models.JSONField(blank=True, default=list)),
                ('icms_base', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('icms_aliquota', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=7)),
                ('icms_valor', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('modal', models.CharField(blank=True, max_length=16)),
                ('tipo_servico', models.CharField(blank=True, max_length=16)),
                ('municipio_inicio', models.CharField(blank=True, max_length=120)),
                ('uf_inicio', models.CharField(blank=True, max_length=2)),
                ('municipio_fim', models.CharField(blank=True, max_length=120)),
                ('uf_fim', models.CharField(blank=True, max_length=2)),
                ('emit_json', models.JSONField(blank=True, default=dict)),
                ('rem_json', models.JSONField(blank=True, default=dict)),
                ('dest_json', models.JSONField(blank=True, default=dict)),
                ('exped_json', models.JSONField(blank=True, default=dict)),
                ('receb_json', models.JSONField(blank=True, default=dict)),
                ('tomador_json', models.JSONField(blank=True, default=dict)),
                ('totais_json', models.JSONField(blank=True, default=dict)),
                ('imposto_json', models.JSONField(blank=True, default=dict)),
                ('prot_json', models.JSONField(blank=True, default=dict)),
                ('reforma_e_outros_json', models.JSONField(blank=True, default=dict)),
                ('chaves_nfe_vinculadas', models.JSONField(blank=True, default=list)),
                ('importado', models.BooleanField(default=True)),
                ('origem_externa', models.BooleanField(default=True)),
                ('historico', models.BooleanField(default=True)),
                ('nome_arquivo', models.CharField(blank=True, max_length=255)),
                ('importado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'empresa_tomadora',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='ctes_historicos_importados_como_tomadora',
                        to='cadastros.empresa',
                    ),
                ),
                (
                    'transportadora',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='ctes_historicos_importados',
                        to='cadastros.transportadora',
                    ),
                ),
            ],
            options={
                'verbose_name': 'CT-e importado (histórico)',
                'verbose_name_plural': 'CT-e importados (histórico)',
                'ordering': ['-dh_emissao', '-id'],
            },
        ),
        migrations.CreateModel(
            name='EventoCTeHistoricoImportado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chave_acesso', models.CharField(db_index=True, max_length=44)),
                ('tipo_evento', models.CharField(db_index=True, max_length=16)),
                ('protocolo_evento', models.CharField(blank=True, max_length=30)),
                ('id_evento', models.CharField(blank=True, max_length=80)),
                ('sequencial_evento', models.PositiveSmallIntegerField(default=0)),
                ('data_evento', models.DateTimeField(blank=True, null=True)),
                ('evento_json', models.JSONField(blank=True, default=dict)),
                ('nome_arquivo', models.CharField(blank=True, max_length=255)),
                ('importado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'cte',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='eventos',
                        to='fiscal.ctehistoricoimportado',
                    ),
                ),
            ],
            options={
                'ordering': ['-importado_em', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='eventoctehistoricoimportado',
            constraint=models.UniqueConstraint(
                fields=('cte', 'tipo_evento', 'protocolo_evento', 'id_evento'),
                name='uniq_cte_hist_evento_dedup',
            ),
        ),
    ]

