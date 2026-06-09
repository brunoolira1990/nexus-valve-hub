# Comercial 2.4 — vínculo Vendedor ↔ Colaborador

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0010_colaborador'),
        ('comercial', '0025_vendedor_e_fk_comercial'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendedor',
            name='colaborador',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vendedores',
                to='cadastros.colaborador',
            ),
        ),
    ]
