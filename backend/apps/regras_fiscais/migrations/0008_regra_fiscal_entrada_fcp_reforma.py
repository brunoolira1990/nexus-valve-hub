from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0007_rename_cenario_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='fcp_aplicavel',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_fcp',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_fcp_st',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='reducao_bc_fcp',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='valor_fcp_unidade',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='reforma_tributaria',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
