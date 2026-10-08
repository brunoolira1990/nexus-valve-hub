import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0012_regrafiscalsaida_recomendacoes_nfe'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('comercial', '0016_proposta_homologacao_fiscal'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomologacaoFiscalPropostaEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'tipo_evento',
                    models.CharField(
                        choices=[
                            ('INICIADA', 'Homologação iniciada'),
                            ('RECALCULADA', 'Homologação recalculada'),
                            ('APROVADA', 'Homologação aprovada'),
                            ('REPROVADA', 'Homologação reprovada'),
                            ('VOLTOU_LEGADO', 'Voltou para regra legada'),
                            ('ALTEROU_CENARIO', 'Cenário fiscal alterado'),
                        ],
                        max_length=32,
                    ),
                ),
                ('status_resultante', models.CharField(max_length=32)),
                ('usar_cenario_fiscal_saida', models.BooleanField(default=False)),
                ('cenario_fiscal_saida_nome', models.CharField(blank=True, max_length=255)),
                ('resumo', models.JSONField(blank=True, null=True)),
                ('itens', models.JSONField(blank=True, null=True)),
                ('observacao', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'cenario_fiscal_saida',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='homologacao_fiscal_eventos',
                        to='regras_fiscais.cenariofiscalsaida',
                    ),
                ),
                (
                    'criado_por',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='homologacao_fiscal_proposta_eventos',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'proposta',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='homologacao_fiscal_eventos',
                        to='comercial.proposta',
                    ),
                ),
            ],
            options={
                'ordering': ['-criado_em', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='homologacaofiscalpropostaevento',
            index=models.Index(fields=['proposta', '-criado_em'], name='comercial_h_proposta_criado_idx'),
        ),
    ]
