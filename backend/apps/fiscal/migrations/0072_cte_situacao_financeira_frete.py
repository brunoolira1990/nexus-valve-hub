# Generated manually for situacao_financeira_frete on CTeHistoricoImportado

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0071_cte_frete_financeiro_rateio'),
    ]

    operations = [
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='situacao_financeira_frete',
            field=models.CharField(
                choices=[
                    ('PENDENTE', 'Pendente de definição'),
                    ('A_PAGAR', 'A pagar (gerar CP)'),
                    ('PAGO_AVISTA', 'Pago à vista'),
                    ('NAO_GERA_CP', 'Não gera Contas a Pagar'),
                    ('CP_GERADO', 'CP gerado'),
                ],
                db_index=True,
                default='PENDENTE',
                help_text='Disposição financeira do frete tomado (independente da apuração fiscal).',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='situacao_financeira_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='situacao_financeira_obs',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='situacao_financeira_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ctes_historicos_situacao_financeira',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
