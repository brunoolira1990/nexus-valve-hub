from django.db import migrations


def _norm_digits(value):
    return ''.join(c for c in str(value or '') if c.isdigit())


def _party_doc(party):
    if not isinstance(party, dict):
        return ''
    return _norm_digits(party.get('CNPJ') or party.get('CPF') or '')


def _tomador_doc(cte):
    tom = cte.tomador_json if isinstance(cte.tomador_json, dict) else {}
    doc = _party_doc(tom)
    if len(doc) == 14:
        return doc

    tp_toma = str(tom.get('tpToma') or tom.get('toma') or '').strip()
    if tp_toma == '0':
        return _party_doc(cte.rem_json)
    if tp_toma == '1':
        return _party_doc(cte.exped_json)
    if tp_toma == '2':
        return _party_doc(cte.receb_json)
    if tp_toma == '3':
        return _party_doc(cte.dest_json)
    return ''


def forwards(apps, schema_editor):
    Empresa = apps.get_model('cadastros', 'Empresa')
    CTeHistorico = apps.get_model('fiscal', 'CTeHistoricoImportado')

    empresas_por_doc = {}
    for emp in Empresa.objects.only('id', 'cnpj'):
        doc = _norm_digits(emp.cnpj)
        if len(doc) == 14:
            empresas_por_doc[doc] = emp.id

    for cte in CTeHistorico.objects.all().iterator(chunk_size=500):
        doc_tomador = _tomador_doc(cte)
        empresa_tomadora_id = empresas_por_doc.get(doc_tomador)
        if empresa_tomadora_id:
            cte.empresa_tomadora_id = empresa_tomadora_id
            cte.papel_empresa_no_documento = 'tomador'
            cte.save(update_fields=['empresa_tomadora', 'papel_empresa_no_documento'])


def backwards(apps, schema_editor):
    # Migração corretiva sem rollback automático.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('fiscal', '0008_reclassificar_nf_saida_historica_compra'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
