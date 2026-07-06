from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('corridas', '0001_initial'),
        ('fiscal', '0058_rename_fiscal_nfe__configu_inut_idx_fiscal_nfei_configu_7378d3_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemNFeEntradaConferenciaCorridaSplit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveSmallIntegerField(default=1)),
                ('corrida', models.CharField(blank=True, max_length=64)),
                ('lote', models.CharField(blank=True, max_length=64)),
                ('quantidade', models.DecimalField(decimal_places=3, max_digits=14)),
                ('quantidade_aplicada', models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True)),
                (
                    'corrida_estoque',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='splits_conferencia',
                        to='corridas.corrida',
                    ),
                ),
                (
                    'estoque_corrida',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='splits_conferencia',
                        to='fiscal.estoquecorrida',
                    ),
                ),
                (
                    'item_conferencia',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='corridas_split',
                        to='fiscal.itemnfeentradaconferencia',
                    ),
                ),
            ],
            options={
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='itemnfeentradaconferenciacorridasplit',
            constraint=models.UniqueConstraint(
                fields=('item_conferencia', 'ordem'),
                name='uniq_item_conf_corrida_split_ordem',
            ),
        ),
    ]
