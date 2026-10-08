from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0004_rename_regras_fisc_cfop_orig_idx_regras_fisc_cfop_or_f2b946_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='modalidade_bc_icms',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_icms',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='reducao_bc_icms',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='motivo_desoneracao_icms',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='codigo_beneficio_icms',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='icms_st_aplicavel',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='cst_icms_st_esperado',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_icms_st',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='mva_st',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='reducao_bc_st',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='tipo_calculo_ipi',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_ipi',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='valor_ipi_unidade',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='enquadramento_ipi',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='tipo_calculo_pis',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_pis',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='reducao_base_pis',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='valor_minimo_pis_unidade',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_pis_st',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='tipo_calculo_cofins',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_cofins',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='reducao_base_cofins',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='valor_minimo_cofins_unidade',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='aliquota_cofins_st',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
    ]
