# Generated manually for NEXUS — família, rosca/conexão, schedule e modo de código.

import django.db.models.deletion
from django.db import migrations, models


def seed_rosa_padrao(apps, schema_editor):
    RoscaConexao = apps.get_model('produtos', 'RoscaConexao')
    RoscaConexao.objects.get_or_create(
        codigo='',
        defaults={'descricao': 'BSP / padrão da família', 'observacao': '', 'ativo': True},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoscaConexao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(help_text='Vazio = BSP / padrão da família.', max_length=16, unique=True)),
                ('descricao', models.CharField(max_length=128)),
                ('observacao', models.CharField(blank=True, max_length=256)),
                ('ativo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Rosca / Conexão',
                'verbose_name_plural': 'Roscas / Conexões',
                'ordering': ['codigo'],
            },
        ),
        migrations.RunPython(seed_rosa_padrao, migrations.RunPython.noop),
        migrations.CreateModel(
            name='ScheduleEspessura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_schedule', models.CharField(max_length=32, unique=True)),
                ('descricao', models.CharField(blank=True, max_length=128)),
                ('ativo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Schedule / Espessura',
                'ordering': ['codigo_schedule'],
            },
        ),
        migrations.CreateModel(
            name='FamiliaProduto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo_figura', models.CharField(max_length=32, unique=True)),
                ('descricao_base', models.CharField(max_length=512)),
                (
                    'tipo_regra_codigo',
                    models.CharField(
                        choices=[
                            ('BASE_PP', 'Base + polegada principal'),
                            ('BASE_ROSCA_PP', 'Base + rosca/conexão + polegada principal'),
                            ('BASE_DOIS_P', 'Base + duas polegadas (IDs)'),
                            ('BASE_ROSCA_DOIS_P', 'Base + rosca + duas polegadas'),
                            ('BASE_SCHED_PP', 'Base + schedule + polegada principal'),
                            ('BASE_SCHED_DOIS_P', 'Base + schedule + duas polegadas'),
                            ('BASE_UNDERSCORE_P', 'Base + underscore + polegada (ID)'),
                        ],
                        default='BASE_PP',
                        max_length=32,
                    ),
                ),
                ('usa_rosca_conexao', models.BooleanField(default=False)),
                ('usa_schedule', models.BooleanField(default=False)),
                ('usa_polegada_principal', models.BooleanField(default=True)),
                ('usa_polegada_secundaria', models.BooleanField(default=False)),
                (
                    'separador_base_medidas',
                    models.CharField(
                        default='.',
                        help_text='Separador entre prefixo e IDs de polegada; use _ para 6038_005.',
                        max_length=1,
                    ),
                ),
                ('ncm_padrao', models.CharField(blank=True, max_length=16)),
                ('unidade_padrao', models.CharField(blank=True, max_length=16)),
                ('material_base', models.CharField(blank=True, max_length=128)),
                ('pressao_base', models.CharField(blank=True, max_length=64)),
                ('norma_base', models.CharField(blank=True, max_length=128)),
                ('ativo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Família / Figura de produto',
                'verbose_name_plural': 'Famílias / Figuras de produto',
                'ordering': ['codigo_figura'],
            },
        ),
        migrations.AddField(
            model_name='produto',
            name='modo_codigo',
            field=models.CharField(
                choices=[('LEGADO', 'Legado (campos texto figura/sufixo/schedule/polegada)'), ('INTERNO', 'Código interno por família e bases'), ('MANUAL', 'Código manual / fabricante')],
                db_index=True,
                default='LEGADO',
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name='produto',
            name='figura',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name='produto',
            name='sufixo',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name='produto',
            name='schedule',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name='produto',
            name='polegada_principal',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='produto',
            name='familia',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produtos',
                to='produtos.familiaproduto',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='polegada_principal_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produtos_principal',
                to='produtos.polegada',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='polegada_secundaria_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produtos_secundaria',
                to='produtos.polegada',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='rosca_conexao',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produtos',
                to='produtos.roscaconexao',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='schedule_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produtos',
                to='produtos.scheduleespessura',
            ),
        ),
    ]
