from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0015_proposta_cenario_fiscal_saida'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='homologacao_fiscal_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='proposta',
            name='homologacao_fiscal_observacao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='proposta',
            name='homologacao_fiscal_resumo',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='proposta',
            name='homologacao_fiscal_status',
            field=models.CharField(
                choices=[
                    ('NAO_INICIADA', 'Não iniciada'),
                    ('EM_ANALISE', 'Em análise'),
                    ('APROVADA', 'Aprovada'),
                    ('REPROVADA', 'Reprovada'),
                    ('VOLTOU_LEGADO', 'Voltou ao legado'),
                ],
                default='NAO_INICIADA',
                help_text='Fluxo assistido de homologação do cenário fiscal de saída nesta proposta.',
                max_length=32,
            ),
        ),
    ]
