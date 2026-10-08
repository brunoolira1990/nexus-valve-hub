# Merge migration: une os dois ramos 0013 sem reaplicar alterações.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0013_familia_tipo_dimensional_produto_od_mm'),
        ('produtos', '0013_alter_scheduleespessura_options_and_more'),
    ]

    operations = []
