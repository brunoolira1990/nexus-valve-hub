from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('regras_fiscais', '0016_seed_aliquotaicmsuf'),
    ]

    operations = [
        migrations.AddField(
            model_name='aliquotaicmsuf',
            name='vigencia_inicio',
            field=models.DateField(
                blank=True,
                help_text='Data em que esta alíquota passou a valer. NULL = vigência não informada.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='aliquotaicmsuf',
            name='atualizado_por',
            field=models.ForeignKey(
                blank=True,
                help_text='Última pessoa que alterou a linha (seed/migração fica vazio).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='aliquotas_uf_atualizadas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='atualizado por',
            ),
        ),
        migrations.AlterField(
            model_name='aliquotaicmsuf',
            name='aliquota_fcp',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='FCP destino. NULL = não cadastrado; o DIFAL não presume FCP.',
                max_digits=7,
                null=True,
            ),
        ),
    ]
