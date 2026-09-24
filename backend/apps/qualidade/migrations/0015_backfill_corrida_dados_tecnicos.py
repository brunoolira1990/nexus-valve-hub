from django.db import migrations, models

def backfill_corrida_dados_tecnicos(apps, schema_editor):
    ItemCertificadoFornecedorCorrida = apps.get_model('qualidade', 'ItemCertificadoFornecedorCorrida')
    ItemCertificadoFornecedorEntrada = apps.get_model('qualidade', 'ItemCertificadoFornecedorEntrada')

    corridas = ItemCertificadoFornecedorCorrida.objects.all()
    for corrida in corridas:
        pai = corrida.item_certificado
        if not pai:
            continue
        composicao = getattr(pai, 'composicao_json', None) or {}
        ensaio_tracao = getattr(pai, 'ensaio_tracao_json', None) or {}
        ensaio_impacto = getattr(pai, 'ensaio_impacto_json', None) or {}

        precisa_atualizar = False
        if not getattr(corrida, 'composicao_json', None) and any(
            str(v or '').strip() for v in (composicao or {}).values()
        ):
            corrida.composicao_json = composicao
            precisa_atualizar = True
        if not getattr(corrida, 'ensaio_tracao_json', None) and any(
            str(v or '').strip() for v in (ensaio_tracao or {}).values()
        ):
            corrida.ensaio_tracao_json = ensaio_tracao
            precisa_atualizar = True
        if not getattr(corrida, 'ensaio_impacto_json', None) and any(
            str(v or '').strip() for v in (ensaio_impacto or {}).values()
        ):
            corrida.ensaio_impacto_json = ensaio_impacto
            precisa_atualizar = True

        if precisa_atualizar:
            corrida.save(update_fields=[
                'composicao_json',
                'ensaio_tracao_json',
                'ensaio_impacto_json',
            ])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0014_itemcertificadofornecedorcorrida_composicao_json_and_more'),
    ]

    operations = [
        migrations.RunPython(
            backfill_corrida_dados_tecnicos,
            reverse_code=reverse_noop,
        ),
    ]