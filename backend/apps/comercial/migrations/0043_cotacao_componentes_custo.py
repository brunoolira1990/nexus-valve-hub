from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('comercial', '0042_cotacao_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='preco_unitario_bruto',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='desconto',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='unidade_cotada',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='fator_conversao',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='frete_tipo_codigo',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='ipi_custo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='icms_st_custo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='outros_tributos_custo',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='cotacaofornecedorrespostaitem',
            name='despesas_adicionais',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddConstraint(
            model_name='cotacaofornecedorrespostaitem',
            constraint=models.CheckConstraint(
                condition=models.Q(('preco_unitario_bruto__isnull', True)) | models.Q(('preco_unitario_bruto__gte', Decimal('0'))),
                name='cot_resp_preco_bruto_nao_neg',
            ),
        ),
        migrations.AddConstraint(
            model_name='cotacaofornecedorrespostaitem',
            constraint=models.CheckConstraint(
                condition=models.Q(('desconto__isnull', True)) | models.Q(('desconto__gte', Decimal('0'))),
                name='cot_resp_desconto_nao_neg',
            ),
        ),
        migrations.AddConstraint(
            model_name='cotacaofornecedorrespostaitem',
            constraint=models.CheckConstraint(
                condition=models.Q(('fator_conversao__isnull', True)) | models.Q(('fator_conversao__gt', Decimal('0'))),
                name='cot_resp_fator_conversao_positivo',
            ),
        ),
    ]
