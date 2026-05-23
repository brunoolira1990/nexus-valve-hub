from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0020_nfe_saida_dados_complementares'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='pedido_cliente_numero',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='pedido_cliente_observacao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='informacoes_fisco',
            field=models.TextField(blank=True, help_text='Informações ao Fisco (prévia/preparatório).'),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='observacoes_internas',
            field=models.TextField(blank=True, help_text='Observações internas ERP — não saem no XML/DANFE.'),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='especie_volumes',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='marca_volumes',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='numeracao_volumes',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='placa_veiculo',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='uf_veiculo',
            field=models.CharField(blank=True, max_length=2),
        ),
        migrations.AddField(
            model_name='itemnfesaida',
            name='pedido_cliente_numero',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemnfesaida',
            name='pedido_cliente_item',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemnfesaida',
            name='observacao_item',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='itemnfesaida',
            name='informacao_adicional_item',
            field=models.TextField(blank=True),
        ),
    ]
