from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0007_item_certificado_qualidade_inclusao_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='numero_certificado_fornecedor_item',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='data_certificado_fornecedor_item',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='pagina_certificado_fornecedor',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='observacao_origem_certificado',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='componentecertificadofornecedorentrada',
            name='numero_certificado_fornecedor_componente',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='numero_certificado_fornecedor_item_snapshot',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemcertificadoqualidadecomponente',
            name='numero_certificado_fornecedor_componente_snapshot',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
