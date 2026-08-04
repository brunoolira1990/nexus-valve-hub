# Garante remoção do UNIQUE global em corridas_corrida.numero (PostgreSQL).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('corridas', '0002_corrida_numero_por_produto'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                # Nomes comuns gerados pelo Django/Postgres para CharField(unique=True).
                'ALTER TABLE corridas_corrida DROP CONSTRAINT IF EXISTS corridas_corrida_numero_key;'
                'DROP INDEX IF EXISTS corridas_corrida_numero_key;'
                'DROP INDEX IF EXISTS corridas_corrida_numero_uniq;'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
