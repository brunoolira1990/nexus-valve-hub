# Comercial/Cadastros 2.4 — colaboradores e responsáveis internos

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cadastros', '0009_alter_cliente_dias_parcelas_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Colaborador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('codigo', models.CharField(blank=True, db_index=True, max_length=32)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('telefone', models.CharField(blank=True, max_length=32)),
                ('ativo', models.BooleanField(default=True)),
                ('eh_vendedor', models.BooleanField(default=False)),
                ('eh_comprador', models.BooleanField(default=False)),
                ('eh_responsavel_fiscal', models.BooleanField(default=False)),
                ('eh_responsavel_financeiro', models.BooleanField(default=False)),
                ('eh_responsavel_estoque', models.BooleanField(default=False)),
                ('eh_responsavel_qualidade', models.BooleanField(default=False)),
                ('eh_administrador', models.BooleanField(default=False)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'usuario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='colaborador_vinculado',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Colaborador',
                'verbose_name_plural': 'Colaboradores',
                'ordering': ['nome'],
            },
        ),
    ]
