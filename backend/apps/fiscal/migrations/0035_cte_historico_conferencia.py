# Generated manually — ERP 4.0.10.2.2 conferência CT-e importado

from django.conf import settings
from django.db import migrations, models


def backfill_status_conferencia(apps, schema_editor):
    CTe = apps.get_model('fiscal', 'CTeHistoricoImportado')
    for cte in CTe.objects.all().iterator(chunk_size=500):
        if cte.cancelado:
            st = 'CANCELADO'
        elif (cte.cstat or '').strip() in ('100', '100.0'):
            st = 'PROCESSADO'
        else:
            st = 'IMPORTADO'
        CTe.objects.filter(pk=cte.pk).update(status_conferencia=st)


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0034_alocacao_atendimento_modelo_operacional_4010'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='status_conferencia',
            field=models.CharField(
                choices=[
                    ('IMPORTADO', 'Importado'),
                    ('PROCESSADO', 'Processado'),
                    ('PREPARADO', 'Preparado'),
                    ('CONFERIDO', 'Conferido'),
                    ('DIVERGENTE', 'Divergente'),
                    ('IGNORADO', 'Ignorado'),
                    ('CANCELADO', 'Cancelado'),
                ],
                default='IMPORTADO',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='conferido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='conferido_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='ctes_historicos_conferidos',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='observacao_conferencia',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='divergencia_motivo',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='apto_operacional',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='ignorado_operacionalmente',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='checklist_conferencia_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_status_conferencia, migrations.RunPython.noop),
    ]
