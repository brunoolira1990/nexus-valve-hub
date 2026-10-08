# ERP 4.0.14.x — Sequência persistente para codigo_figura automático (padrão NNNN).
#
# Backup antes de aplicar em produção: pg_dump ou snapshot do banco.
# Rollback: python manage.py migrate produtos 0026
#   — remove FamiliaProdutoCodigoSequencia; códigos já gerados em FamiliaProduto permanecem válidos.

import re

from django.db import migrations, models

_CODIGO_VALIDO = re.compile(r'^\d{4}$')


def inicializar_sequencia_codigo_figura(apps, schema_editor):
    Familia = apps.get_model('produtos', 'FamiliaProduto')
    Seq = apps.get_model('produtos', 'FamiliaProdutoCodigoSequencia')
    max_n = 0
    for cod in Familia.objects.values_list('codigo_figura', flat=True):
        cod = (cod or '').strip()
        if _CODIGO_VALIDO.match(cod):
            max_n = max(max_n, int(cod))
    Seq.objects.create(pk=1, proximo_numero=max_n + 1)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0026_familiaproduto_tipo_composicao_fisica_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FamiliaProdutoCodigoSequencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'proximo_numero',
                    models.PositiveIntegerField(
                        default=1,
                        help_text='Próximo inteiro a formatar como codigo_figura (4 dígitos). Não reutiliza excluídos.',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Sequência código figura (família)',
                'verbose_name_plural': 'Sequência código figura (família)',
            },
        ),
        migrations.RunPython(inicializar_sequencia_codigo_figura, noop_reverse),
    ]
