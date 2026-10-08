# Heat/corrida number can repeat across different products.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('corridas', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='corrida',
            name='numero',
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AddConstraint(
            model_name='corrida',
            constraint=models.UniqueConstraint(
                fields=('numero', 'produto'),
                name='corridas_corrida_numero_produto_uniq',
            ),
        ),
    ]
