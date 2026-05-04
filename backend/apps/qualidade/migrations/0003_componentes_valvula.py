# Suporte a certificado de válvula por componentes

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qualidade', '0002_certificado_qualidade'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcertificadoqualidade',
            name='tipo_dados_tecnicos',
            field=models.CharField(
                choices=[('PADRAO_ITEM', 'Dados por item'), ('VALVULA_COMPONENTES', 'Dados por componentes de válvula')],
                default='PADRAO_ITEM',
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name='ItemCertificadoQualidadeComponente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(default=1)),
                ('nome_componente', models.CharField(max_length=120)),
                ('descricao_componente', models.CharField(blank=True, max_length=255)),
                ('norma', models.CharField(blank=True, max_length=128)),
                ('corrida', models.CharField(blank=True, max_length=64)),
                ('revisao_corrida', models.CharField(blank=True, max_length=64)),
                ('quantidade', models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True)),
                ('composicao_json', models.JSONField(blank=True, default=dict)),
                ('ensaio_tracao_json', models.JSONField(blank=True, default=dict)),
                ('ensaio_impacto_json', models.JSONField(blank=True, default=dict)),
                ('observacoes', models.TextField(blank=True)),
                ('ativo', models.BooleanField(default=True)),
                ('item_certificado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='componentes', to='qualidade.itemcertificadoqualidade')),
            ],
            options={
                'ordering': ['ordem', 'id'],
            },
        ),
    ]
