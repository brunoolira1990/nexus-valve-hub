from django.db import migrations, models

from apps.regras_fiscais.aliquotas_uf_seed import ALICOTAS_ICMS_UF


def aplicar_regime_base(apps, schema_editor):
    """Espelha o regime de base (única × dupla) do seed nas linhas já cadastradas."""
    AliquotaIcmsUF = apps.get_model('regras_fiscais', 'AliquotaIcmsUF')
    for uf, dados in ALICOTAS_ICMS_UF.items():
        AliquotaIcmsUF.objects.filter(uf=uf).update(usa_base_dupla=dados['base_dupla'] is True)


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0018_aliquotaicmsuf_tabela_oficial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aliquotaicmsuf',
            name='usa_base_dupla',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'True = DIFAL calculado "por dentro" (base dupla): a BC do estado de destino é '
                    'recomposta dentro do próprio ICMS. False = base única: DIFAL sobre a BC da '
                    'operação pela diferença de alíquotas.'
                ),
                verbose_name='usa base dupla',
            ),
        ),
        migrations.RunPython(aplicar_regime_base, migrations.RunPython.noop),
    ]
