from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0004_certificado_fornecedor_entrada'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='certificado_fornecedor_origem_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='codigo_item_fornecedor_snapshot',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='corrida_snapshot',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='descricao_item_fornecedor_snapshot',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='fornecedor_nome_snapshot',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='item_certificado_fornecedor_origem_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='lote_snapshot',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='nf_entrada_snapshot',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
