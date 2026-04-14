# Generated manually — aplicar com: docker compose exec backend python manage.py migrate cadastros

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0003_cnpj_validators_and_empresa_upload_paths"),
    ]

    operations = [
        migrations.CreateModel(
            name="CondicaoPagamento",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("descricao", models.CharField(max_length=100)),
                ("parcelas", models.IntegerField(default=1)),
                ("dias_entre_parcelas", models.IntegerField(default=30)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["descricao"],
            },
        ),
        migrations.AddField(
            model_name="transportadora",
            name="nome_fantasia",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="inscricao_municipal",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="celular",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="contato",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="valor_km",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10
            ),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="transportadora",
            name="observacoes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="cliente",
            name="inscricao_municipal",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="suframa",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="email_nf",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="cliente",
            name="telefone_alternativo",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="celular",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="limite_credito",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="vendedor_padrao",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="cliente",
            name="bloqueado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cliente",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="cliente",
            name="condicao_pagamento_padrao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clientes_condicao_padrao",
                to="cadastros.condicaopagamento",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="transportadora_padrao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clientes_transportadora_padrao",
                to="cadastros.transportadora",
            ),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="inscricao_municipal",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="suframa",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="email_nf",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="telefone_alternativo",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="celular",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="prazo_entrega",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="condicao_pagamento_padrao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fornecedores_condicao_padrao",
                to="cadastros.condicaopagamento",
            ),
        ),
        migrations.AddField(
            model_name="fornecedor",
            name="transportadora_padrao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fornecedores_transportadora_padrao",
                to="cadastros.transportadora",
            ),
        ),
    ]
