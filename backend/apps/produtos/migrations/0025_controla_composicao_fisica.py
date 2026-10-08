from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0024_alter_familiaproduto_tipo_dimensional_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='familiaproduto',
            name='controla_composicao_fisica',
            field=models.BooleanField(
                default=False,
                help_text='Exige composição por barra na conferência; estoque base em metros.',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='controla_composicao_fisica',
            field=models.BooleanField(default=False),
        ),
    ]
