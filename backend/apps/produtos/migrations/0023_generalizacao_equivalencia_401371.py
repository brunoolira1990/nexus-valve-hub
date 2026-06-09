# ERP 4.0.13.7.1 — generalização composição/equivalência

from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def _migrar_tipos_composicao(apps, schema_editor):
    ProdutoComposicao = apps.get_model('produtos', 'ProdutoComposicao')
    ProdutoComposicao.objects.filter(tipo_composicao='MONTAGEM_COM_SERVICO_INTERNO').update(
        tipo_composicao='MONTAGEM_SERVICO_INTERNO',
    )
    ProdutoComposicao.objects.filter(tipo_composicao='EQUIVALENCIA_FORNECEDOR').update(
        tipo_composicao='MONTAGEM_SIMPLES',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0022_equivalencia_composicao_40137'),
    ]

    operations = [
        migrations.RenameField(
            model_name='produtocomposicao',
            old_name='exige_confirmacao_operacional',
            new_name='exige_confirmacao',
        ),
        migrations.AddField(
            model_name='produtocomposicao',
            name='nome',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='produtocomposicao',
            name='padrao',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='produtocomposicao',
            name='permite_alternativa',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='produtocomposicao',
            name='exige_ordem_montagem',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='produtocomposicao',
            name='tipo_composicao',
            field=models.CharField(
                choices=[
                    ('KIT_COMERCIAL', 'Kit comercial'),
                    ('MONTAGEM_SIMPLES', 'Montagem simples'),
                    ('MONTAGEM_ROSCADA', 'Montagem roscada'),
                    ('MONTAGEM_SOLDADA', 'Montagem soldada'),
                    ('MONTAGEM_SERVICO_INTERNO', 'Montagem com serviço interno'),
                    ('MONTAGEM_TERCEIRIZADA', 'Montagem terceirizada'),
                    ('BENEFICIAMENTO', 'Beneficiamento'),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterModelOptions(
            name='produtocomposicao',
            options={
                'ordering': ['produto_final_id', '-padrao', '-ativo', 'id'],
                'verbose_name': 'Composição de produto',
                'verbose_name_plural': 'Composições de produto',
            },
        ),
        migrations.CreateModel(
            name='ProcessoMontagem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'tipo',
                    models.CharField(
                        choices=[
                            ('encaixe', 'Encaixe'),
                            ('rosca', 'Rosca'),
                            ('flangeamento', 'Flangeamento'),
                            ('solda', 'Solda'),
                            ('corte', 'Corte'),
                            ('usinagem', 'Usinagem'),
                            ('montagem_manual', 'Montagem manual'),
                            ('montagem_terceirizada', 'Montagem terceirizada'),
                            ('outro', 'Outro'),
                        ],
                        max_length=32,
                    ),
                ),
                ('exige_servico', models.BooleanField(default=False)),
                ('exige_fornecedor_servico', models.BooleanField(default=False)),
                ('gera_produto_acabado', models.BooleanField(default=True)),
                ('baixa_componentes', models.BooleanField(default=False)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'composicao',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='processos',
                        to='produtos.produtocomposicao',
                    ),
                ),
            ],
            options={
                'ordering': ['composicao_id', 'id'],
            },
        ),
        migrations.RunPython(_migrar_tipos_composicao, migrations.RunPython.noop),
    ]
