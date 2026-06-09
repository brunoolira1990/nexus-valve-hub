from django.db import migrations, models


def copiar_cfop_para_origem(apps, schema_editor):
    RegraFiscalEntrada = apps.get_model('regras_fiscais', 'RegraFiscalEntrada')
    for regra in RegraFiscalEntrada.objects.exclude(cfop='').iterator():
        if not (regra.cfop_origem or '').strip():
            regra.cfop_origem = (regra.cfop or '').strip()
            regra.save(update_fields=['cfop_origem'])


class Migration(migrations.Migration):

    dependencies = [
        ('regras_fiscais', '0002_regra_fiscal_entrada'),
    ]

    operations = [
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='cfop_origem',
            field=models.CharField(
                blank=True,
                help_text='CFOP informado na NF-e (origem da operação).',
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='cfop_entrada',
            field=models.CharField(
                blank=True,
                help_text='CFOP de entrada/classificação esperado após conferência.',
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='descricao_cenario',
            field=models.CharField(
                blank=True,
                help_text='Rótulo operacional do cenário fiscal (ex.: Compra SP→RJ válvulas).',
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name='regrafiscalentrada',
            name='cfop',
            field=models.CharField(
                blank=True,
                help_text='Legado: espelha cfop_origem na fase de transição.',
                max_length=8,
            ),
        ),
        migrations.AddIndex(
            model_name='regrafiscalentrada',
            index=models.Index(fields=['cfop_origem'], name='regras_fisc_cfop_orig_idx'),
        ),
        migrations.RunPython(copiar_cfop_para_origem, migrations.RunPython.noop),
    ]
