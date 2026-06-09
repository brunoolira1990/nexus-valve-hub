# Generated manually — ERP 4.0.14.8

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0011_cliente_informacoes_complementares_nfe'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='cargo',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='departamento',
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
