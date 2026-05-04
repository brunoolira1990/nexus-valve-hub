# Controle de variações permitidas por família e overrides no produto.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produtos', '0004_familia_tipo_regra_codigo_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='familiaproduto',
            name='conexao_base',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='produto',
            name='ncm_especifico',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='produto',
            name='unidade',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='produto',
            name='unidade_especifica',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.CreateModel(
            name='FamiliaProdutoPolegadaPermitida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('principal', 'Principal'), ('secundaria', 'Secundária'), ('ambas', 'Ambas')], default='ambas', max_length=16)),
                ('ordem', models.PositiveIntegerField(blank=True, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('familia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='polegadas_permitidas', to='produtos.familiaproduto')),
                ('polegada', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='familias_permitidas', to='produtos.polegada')),
            ],
            options={
                'ordering': ['familia_id', 'ordem', 'polegada__codigo'],
            },
        ),
        migrations.CreateModel(
            name='FamiliaProdutoRoscaConexaoPermitida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('padrao_da_familia', models.BooleanField(default=False)),
                ('ativo', models.BooleanField(default=True)),
                ('familia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roscas_permitidas', to='produtos.familiaproduto')),
                ('rosca_conexao', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='familias_permitidas', to='produtos.roscaconexao')),
            ],
            options={
                'ordering': ['familia_id', '-padrao_da_familia', 'rosca_conexao__codigo'],
            },
        ),
        migrations.CreateModel(
            name='FamiliaProdutoSchedulePermitido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('padrao_da_familia', models.BooleanField(default=False)),
                ('ativo', models.BooleanField(default=True)),
                ('familia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules_permitidos', to='produtos.familiaproduto')),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='familias_permitidas', to='produtos.scheduleespessura')),
            ],
            options={
                'ordering': ['familia_id', '-padrao_da_familia', 'schedule__codigo_schedule'],
            },
        ),
        migrations.AddConstraint(
            model_name='familiaprodutopolegadapermitida',
            constraint=models.UniqueConstraint(fields=('familia', 'polegada', 'tipo'), name='uq_familia_polegada_permitida_tipo'),
        ),
        migrations.AddConstraint(
            model_name='familiaprodutoroscaconexaopermitida',
            constraint=models.UniqueConstraint(fields=('familia', 'rosca_conexao'), name='uq_familia_rosca_permitida'),
        ),
        migrations.AddConstraint(
            model_name='familiaprodutoroscaconexaopermitida',
            constraint=models.UniqueConstraint(condition=models.Q(padrao_da_familia=True), fields=('familia',), name='uq_familia_rosca_padrao_unica'),
        ),
        migrations.AddConstraint(
            model_name='familiaprodutoschedulepermitido',
            constraint=models.UniqueConstraint(fields=('familia', 'schedule'), name='uq_familia_schedule_permitido'),
        ),
        migrations.AddConstraint(
            model_name='familiaprodutoschedulepermitido',
            constraint=models.UniqueConstraint(condition=models.Q(padrao_da_familia=True), fields=('familia',), name='uq_familia_schedule_padrao_unico'),
        ),
    ]
