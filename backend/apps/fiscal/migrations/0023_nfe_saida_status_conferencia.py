import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0022_nfe_saida_evento_impostos_atualizados'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='status_conferencia',
            field=models.CharField(
                choices=[
                    ('EM_CONFERENCIA', 'Em conferência'),
                    ('COM_PENDENCIAS', 'Com pendências'),
                    ('CONFERIDA', 'Conferida'),
                    ('PRONTA_PARA_EMISSAO', 'Pronta para emissão'),
                ],
                default='EM_CONFERENCIA',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='conferencia_validada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='conferencia_validada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_saidas_conferencia_validadas',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='conferencia_marcada_pronta_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='conferencia_marcada_pronta_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_saidas_conferencia_prontas',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='conferencia_ultima_mensagem',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='nfesaidaevento',
            name='tipo_evento',
            field=models.CharField(
                choices=[
                    ('RASCUNHO_CRIADO', 'Rascunho criado'),
                    ('VALIDADA', 'Validada (pré-emissão)'),
                    ('AUTORIZACAO_EFEITOS_APLICADOS', 'Efeitos de autorização aplicados (interno)'),
                    ('CANCELAMENTO_EFEITOS_APLICADOS', 'Efeitos de cancelamento aplicados (interno)'),
                    ('CANCELADA', 'Cancelada (interno)'),
                    ('ESTORNO_FATURAMENTO', 'Estorno de faturamento vinculado'),
                    ('IMPOSTOS_ATUALIZADOS', 'Impostos atualizados da regra atual'),
                    ('CONFERENCIA_SALVA', 'Conferência salva'),
                    ('CONFERENCIA_VALIDADA', 'Conferência validada'),
                    ('CONFERENCIA_COM_PENDENCIAS', 'Conferência com pendências'),
                    ('PRONTA_PARA_EMISSAO', 'Pronta para emissão'),
                    ('PRONTIDAO_INVALIDADA', 'Prontidão invalidada'),
                    ('OBSERVACAO', 'Observação'),
                ],
                max_length=40,
            ),
        ),
    ]
