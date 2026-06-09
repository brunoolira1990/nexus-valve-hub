"""ERP 4.0.12 — vínculos opcionais NF-e entrada histórica e CT-e conferido em AlocacaoAtendimento."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0035_cte_historico_conferencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='alocacaoatendimento',
            name='cte_historico_importado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='alocacoes_atendimento',
                to='fiscal.ctehistoricoimportado',
            ),
        ),
        migrations.AddField(
            model_name='alocacaoatendimento',
            name='nf_entrada_historica_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='alocacoes_atendimento',
                to='fiscal.itemnfeentradahistoricaimportada',
            ),
        ),
    ]
