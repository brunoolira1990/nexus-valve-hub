from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0006_certificado_qualidade_numero_rascunho'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='incluir_no_certificado',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='motivo_nao_inclusao',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='observacao_nao_inclusao',
            field=models.TextField(blank=True),
        ),
    ]
