from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('produtos', '0009_familia_ncm_padrao_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='ncm',
            name='aliquota_ipi',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='ncm',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='ncm',
            name='ex_tipi',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='ncm',
            name='fonte',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='ncm',
            name='observacoes',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='ncm',
            name='vigencia_fim',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ncm',
            name='vigencia_inicio',
            field=models.DateField(blank=True, null=True),
        ),
    ]
