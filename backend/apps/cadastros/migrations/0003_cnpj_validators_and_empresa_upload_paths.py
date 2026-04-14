from django.db import migrations, models

import apps.cadastros.utils


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0002_empresa_certificado_e_cnpj_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cliente",
            name="cnpj",
            field=models.CharField(
                max_length=20,
                unique=True,
                validators=[apps.cadastros.utils.validar_cnpj_django],
            ),
        ),
        migrations.AlterField(
            model_name="empresa",
            name="certificado_arquivo",
            field=models.FileField(blank=True, null=True, upload_to="certificados/"),
        ),
        migrations.AlterField(
            model_name="empresa",
            name="cnpj",
            field=models.CharField(
                max_length=20,
                unique=True,
                validators=[apps.cadastros.utils.validar_cnpj_django],
            ),
        ),
        migrations.AlterField(
            model_name="empresa",
            name="logotipo",
            field=models.ImageField(blank=True, null=True, upload_to="logos/"),
        ),
        migrations.AlterField(
            model_name="fornecedor",
            name="cnpj",
            field=models.CharField(
                max_length=20,
                unique=True,
                validators=[apps.cadastros.utils.validar_cnpj_django],
            ),
        ),
    ]
