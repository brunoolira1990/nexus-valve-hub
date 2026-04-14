from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0005_condicao_pagamento_dias_parcelas_array"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="ddd",
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name="cliente",
            name="banco",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="cliente",
            name="agencia",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="conta",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="cliente",
            name="tipo_conta",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="cnae",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="regime_tributario",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="cliente",
            name="integracao_texto",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="ddd",
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="banco",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="agencia",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="conta",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="tipo_conta",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="cnae",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="regime_tributario",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="integracao_texto",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="ddd",
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="suframa",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="email_nf",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="banco",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="agencia",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="conta",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="tipo_conta",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="cnae",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="regime_tributario",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="integracao_texto",
            field=models.TextField(blank=True),
        ),
    ]
