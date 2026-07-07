from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0059_item_nfe_entrada_conferencia_corrida_split'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemNFeEntradaConferenciaEquivalencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveSmallIntegerField(default=1)),
                ('metros', models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True)),
                ('barras', models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True)),
                ('peso_kg', models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True)),
                ('peso_por_metro_utilizado', models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True)),
                (
                    'item_conferencia',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='equivalencias',
                        to='fiscal.itemnfeentradaconferencia',
                    ),
                ),
            ],
            options={
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='itemnfeentradaconferenciaequivalencia',
            constraint=models.UniqueConstraint(
                fields=('item_conferencia', 'ordem'),
                name='uniq_item_conf_equivalencia_ordem',
            ),
        ),
    ]
