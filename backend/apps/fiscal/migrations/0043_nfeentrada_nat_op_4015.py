# ERP 4.0.15.0 Parte 2B — natOp para XML NF-e entrada própria

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0042_nfentrada_entrada_propria_emitida_4015'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentrada',
            name='nat_op',
            field=models.CharField(blank=True, max_length=60),
        ),
    ]
