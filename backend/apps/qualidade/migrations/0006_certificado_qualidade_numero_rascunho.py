from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0005_item_certificado_qualidade_origem_fornecedor'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='certificadoqualidade',
            name='uq_certificado_qualidade_numero_serie',
        ),
        migrations.AlterField(
            model_name='certificadoqualidade',
            name='numero',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddConstraint(
            model_name='certificadoqualidade',
            constraint=models.UniqueConstraint(
                condition=~Q(numero=''),
                fields=('numero', 'serie'),
                name='uq_certificado_qualidade_numero_serie',
            ),
        ),
    ]
