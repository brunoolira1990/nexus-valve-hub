from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0008_multiplos_certificados_fornecedor_por_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='componentecertificadofornecedorentrada',
            name='lote',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]

