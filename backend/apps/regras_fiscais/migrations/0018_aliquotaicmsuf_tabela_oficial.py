from django.db import migrations

from apps.regras_fiscais.aliquotas_uf_seed import ALICOTAS_ICMS_UF


def atualizar_aliquotas_uf(apps, schema_editor):
    """Aplica a tabela oficial 2026 sobre linhas já existentes (idempotente)."""
    AliquotaIcmsUF = apps.get_model('regras_fiscais', 'AliquotaIcmsUF')
    for uf, dados in ALICOTAS_ICMS_UF.items():
        AliquotaIcmsUF.objects.update_or_create(
            uf=uf,
            defaults={
                'aliquota_interna': str(dados['interna']),
                'aliquota_interestadual': str(dados['interestadual']),
                'aliquota_fcp': str(dados['fcp']) if dados['fcp'] is not None else None,
                'ativo': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0017_aliquotaicmsuf_auditoria'),
    ]

    operations = [
        migrations.RunPython(atualizar_aliquotas_uf, migrations.RunPython.noop),
    ]
