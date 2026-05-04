from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("produtos", "0005_familia_variacoes_permitidas"),
    ]

    operations = [
        migrations.AddField(
            model_name="familiaproduto",
            name="comprimento_padrao_barra_m",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="densidade",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="observacoes_conversao",
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="peso_por_chapa_kg",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="peso_por_metro_kg",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="peso_por_peca_kg",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="tipo_controle_unidade",
            field=models.CharField(
                choices=[
                    ("PECA", "Peça"),
                    ("DIMENSIONAL", "Dimensional"),
                    ("PESO", "Peso"),
                    ("LINEAR", "Linear"),
                    ("LINEAR_PESO", "Linear + Peso"),
                    ("CHAPA", "Chapa"),
                    ("TUBO", "Tubo"),
                    ("BARRA", "Barra"),
                    ("PERFIL", "Perfil"),
                ],
                default="PECA",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="tipo_fisico",
            field=models.CharField(
                choices=[
                    ("PECA", "Peça"),
                    ("TUBO", "Tubo"),
                    ("BARRA_REDONDA", "Barra redonda"),
                    ("BARRA_CHATA", "Barra chata"),
                    ("BARRA_SEXTAVADA", "Barra sextavada"),
                    ("CHAPA", "Chapa"),
                    ("DISCO", "Disco"),
                    ("PERFIL", "Perfil"),
                    ("CANTONEIRA", "Cantoneira"),
                    ("OUTRO", "Outro"),
                ],
                default="PECA",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="unidade_compra_padrao",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="unidade_estoque_padrao",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="unidade_fiscal_padrao",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="unidade_venda_padrao",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="unidades_compra_permitidas",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="unidades_venda_permitidas",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="familiaproduto",
            name="usa_conversao_dimensional",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="produto",
            name="comprimento_padrao_barra_m",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="produto",
            name="densidade",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="produto",
            name="peso_por_chapa_kg",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="produto",
            name="peso_por_metro_kg",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="produto",
            name="peso_por_peca_kg",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="produto",
            name="tipo_controle_unidade",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PECA", "Peça"),
                    ("DIMENSIONAL", "Dimensional"),
                    ("PESO", "Peso"),
                    ("LINEAR", "Linear"),
                    ("LINEAR_PESO", "Linear + Peso"),
                    ("CHAPA", "Chapa"),
                    ("TUBO", "Tubo"),
                    ("BARRA", "Barra"),
                    ("PERFIL", "Perfil"),
                ],
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="produto",
            name="tipo_fisico",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PECA", "Peça"),
                    ("TUBO", "Tubo"),
                    ("BARRA_REDONDA", "Barra redonda"),
                    ("BARRA_CHATA", "Barra chata"),
                    ("BARRA_SEXTAVADA", "Barra sextavada"),
                    ("CHAPA", "Chapa"),
                    ("DISCO", "Disco"),
                    ("PERFIL", "Perfil"),
                    ("CANTONEIRA", "Cantoneira"),
                    ("OUTRO", "Outro"),
                ],
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="produto",
            name="unidade_compra_padrao",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="produto",
            name="unidade_estoque",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="produto",
            name="unidade_fiscal",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="produto",
            name="unidade_venda_padrao",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="produto",
            name="unidades_venda_permitidas",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="produto",
            name="usa_conversao_dimensional",
            field=models.BooleanField(default=False),
        ),
    ]
