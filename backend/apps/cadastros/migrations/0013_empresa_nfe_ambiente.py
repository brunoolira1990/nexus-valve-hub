from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0012_colaborador_cargo_departamento'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='nfe_ambiente',
            field=models.CharField(
                choices=[('homologacao', 'Homologação'), ('producao', 'Produção')],
                default='homologacao',
                help_text='Ambiente fiscal NF-e desejado para emissão desta empresa.',
                max_length=16,
            ),
        ),
    ]
