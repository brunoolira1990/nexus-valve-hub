from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0009_componente_certificado_fornecedor_lote'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='lote',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='origem_observacoes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='origem_rastreabilidade_tipo',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='origem_status_tecnico',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='produto_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
