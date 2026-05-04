import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0005_cte_historico_importado'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='papel_empresa_no_documento',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='empresa_destinataria',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ctes_historicos_importados_como_destinataria',
                to='cadastros.empresa',
            ),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='empresa_recebedora',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ctes_historicos_importados_como_recebedora',
                to='cadastros.empresa',
            ),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='fornecedor_remetente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ctes_historicos_importados_como_remetente',
                to='cadastros.fornecedor',
            ),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='papel_empresa_no_documento',
            field=models.CharField(blank=True, max_length=32),
        ),
    ]

