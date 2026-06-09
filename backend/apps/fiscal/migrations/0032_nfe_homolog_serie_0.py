"""Homologação NF-e: série 900 → 0 (faixa SEFAZ 0–889)."""

from django.db import migrations, models


def migrar_serie_homolog_900_para_0(apps, schema_editor):
    Config = apps.get_model('fiscal', 'NFeNumeracaoConfiguracao')
    for cfg in Config.objects.filter(ambiente='homologacao', serie='900'):
        existente = Config.objects.filter(
            empresa_id=cfg.empresa_id,
            modelo_documento=cfg.modelo_documento,
            ambiente='homologacao',
            serie='0',
        ).first()
        if existente:
            if int(cfg.proximo_numero or 0) > int(existente.proximo_numero or 0):
                existente.proximo_numero = cfg.proximo_numero
                existente.save(update_fields=['proximo_numero'])
            cfg.delete()
        else:
            cfg.serie = '0'
            cfg.save(update_fields=['serie'])


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0031_nfe_xml_debug_campos'),
    ]

    operations = [
        migrations.RunPython(migrar_serie_homolog_900_para_0, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='nfenumeracaoconfiguracao',
            name='serie',
            field=models.CharField(default='0', max_length=3),
        ),
    ]
