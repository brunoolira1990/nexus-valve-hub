from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('produtos', '0008_alter_familiaproduto_separador_base_medidas_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='familiaproduto',
            name='ncm_padrao_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='familias_padrao',
                to='produtos.ncm',
            ),
        ),
        migrations.RunSQL(
            sql=(
                "UPDATE produtos_familiaproduto f "
                "SET ncm_padrao_fk_id = n.id "
                "FROM produtos_ncm n "
                "WHERE regexp_replace(COALESCE(f.ncm_padrao, ''), '[^0-9A-Za-z]', '', 'g') = "
                "regexp_replace(COALESCE(n.codigo, ''), '[^0-9A-Za-z]', '', 'g')"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RemoveField(
            model_name='familiaproduto',
            name='ncm_padrao',
        ),
        migrations.RenameField(
            model_name='familiaproduto',
            old_name='ncm_padrao_fk',
            new_name='ncm_padrao',
        ),
    ]
