from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0010_rename_regras_fisc_ativo_p_saida_idx_regras_fisc_ativo_e9258d_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrafiscalsaida',
            name='deduzir_icms_base_pis',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='regrafiscalsaida',
            name='deduzir_icms_base_cofins',
            field=models.BooleanField(default=False),
        ),
    ]
