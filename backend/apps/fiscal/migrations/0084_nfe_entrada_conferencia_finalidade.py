from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0083_nfe_entrada_conferencia_chegada'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentradaconferencia',
            name='finalidade_entrada',
            field=models.CharField(
                blank=True,
                choices=[
                    ('COMPRA_REVENDA', 'Comprar para Revenda'),
                    ('CONSUMO_PROPRIIO', 'Uso e Consumo / Ativo'),
                    ('INDUSTRIALIZACAO', 'Industrialização / Insumo'),
                    ('DEVOLUCAO_VENDA', 'Devolução de Venda'),
                    ('BONIFICACAO', 'Bonificação Recebida'),
                    ('FRETE_TRANSPORTE', 'Frete / Transporte'),
                    ('OUTROS', 'Outros'),
                ],
                default='',
                help_text='Definida pelo operador ao iniciar. Alimenta o match fiscal.',
                max_length=32,
            ),
        ),
    ]
