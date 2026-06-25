from django.db import migrations, models


def marcar_ie_isento_cadastros_antigos(apps, schema_editor):
    Cliente = apps.get_model('cadastros', 'Cliente')
    for cliente in Cliente.objects.all().only('id', 'ie', 'ie_isento'):
        ie = (cliente.ie or '').strip().upper()
        if ie in ('ISENTO', 'ISENTA'):
            Cliente.objects.filter(pk=cliente.pk).update(ie_isento=True)


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0013_empresa_nfe_ambiente'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='ie_isento',
            field=models.BooleanField(
                default=False,
                help_text='Cliente isento de Inscrição Estadual (indIEDest=2 na NF-e).',
            ),
        ),
        migrations.RunPython(marcar_ie_isento_cadastros_antigos, migrations.RunPython.noop),
    ]
