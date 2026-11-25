from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0084_nfe_entrada_conferencia_finalidade'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='ncm_efetivo',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='cfop_entrada_efetivo',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='cst_icms_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='csosn_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='cst_ipi_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='cst_pis_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='cst_cofins_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='cst_icms_st_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='origem_mercadoria_efetivo',
            field=models.CharField(blank=True, max_length=2),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='modalidade_bc_icms_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='codigo_beneficio_efetivo',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='motivo_desoneracao_efetivo',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='base_icms_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_icms_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_icms_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='reducao_bc_icms_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='base_icms_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_icms_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_icms_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='mva_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='reducao_bc_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_fcp_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_fcp_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_fcp_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_fcp_st_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='base_ipi_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_ipi_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_ipi_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='base_pis_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_pis_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_pis_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='reducao_base_pis_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='base_cofins_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='aliquota_cofins_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='valor_cofins_efetivo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='reducao_base_cofins_efetivo',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentradaconferencia',
            name='motivo_ajuste_fiscal',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='ItemConferenciaFiscalOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campo', models.CharField(max_length=64)),
                ('valor_anterior', models.CharField(blank=True, max_length=120)),
                ('valor_novo', models.CharField(blank=True, max_length=120)),
                ('motivo', models.TextField()),
                ('usuario_nome', models.CharField(blank=True, max_length=150)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('snapshot_regra', models.JSONField(blank=True, default=dict)),
                (
                    'item_conferencia',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='fiscal_overrides',
                        to='fiscal.itemnfeentradaconferencia',
                    ),
                ),
                (
                    'usuario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='ajustes_fiscais_conferencia',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-criado_em'],
                'indexes': [
                    models.Index(
                        fields=['item_conferencia', '-criado_em'],
                        name='fiscal_over_item_criado_idx',
                    ),
                ],
                'permissions': [
                    ('can_adjust_fiscal_classification', 'Pode ajustar classificação fiscal'),
                ],
            },
        ),
    ]
