from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0049_nfe_destinada_manifestacao_4015'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentradahistoricaimportada',
            name='xml_conteudo',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='ctehistoricoimportado',
            name='xml_conteudo',
            field=models.TextField(blank=True),
        ),
    ]
