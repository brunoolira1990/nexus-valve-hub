from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0004_proposta_avulsa_and_cost_breakdown'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='uf_origem',
            field=models.CharField(blank=True, max_length=2),
        ),
        migrations.AddField(
            model_name='proposta',
            name='uf_destino_avulso',
            field=models.CharField(blank=True, help_text='UF destino quando o cliente é avulso (sem cadastro com UF).', max_length=2),
        ),
        migrations.AddField(
            model_name='proposta',
            name='operacao_fiscal',
            field=models.CharField(default='Saída', max_length=16),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='ipi_entrada_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='icms_saida_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='pis_saida_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='cofins_saida_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='ipi_saida_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='regra_fiscal_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='irpj_estimado_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='csll_estimada_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='comissao_percentual',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='frete_saida',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='outras_despesas_saida',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
