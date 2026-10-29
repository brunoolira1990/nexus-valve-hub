from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0014_frete_transporte_tipo_operacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='AliquotaIcmsUF',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uf', models.CharField(max_length=2, unique=True)),
                ('alias', models.CharField(blank=True, max_length=32)),
                ('aliquota_interna', models.DecimalField(decimal_places=4, max_digits=7)),
                (
                    'aliquota_interestadual',
                    models.DecimalField(
                        decimal_places=4,
                        help_text='Alíquota interestadual de/para a UF (12% Sul/Sudeste, 7% demais, 4% áreas incentivadas).',
                        max_digits=7,
                    ),
                ),
                ('aliquota_fcp', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Alíquota ICMS por UF',
                'verbose_name_plural': 'Alíquotas ICMS por UF',
                'ordering': ['uf'],
            },
        ),
    ]
