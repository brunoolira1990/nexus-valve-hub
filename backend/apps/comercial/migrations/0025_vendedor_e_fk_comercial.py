# Comercial 2.3.2 — cadastro de vendedor e FK opcional em proposta/pedido

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('comercial', '0024_sequencia_comercial_diaria'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vendedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('codigo', models.CharField(blank=True, db_index=True, max_length=32)),
                ('ativo', models.BooleanField(default=True)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('telefone', models.CharField(blank=True, max_length=32)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'usuario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='vendedor_comercial',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Vendedor',
                'verbose_name_plural': 'Vendedores',
                'ordering': ['nome'],
            },
        ),
        migrations.AddField(
            model_name='proposta',
            name='vendedor_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='propostas',
                to='comercial.vendedor',
            ),
        ),
        migrations.AddField(
            model_name='pedidovenda',
            name='vendedor_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pedidos_venda',
                to='comercial.vendedor',
            ),
        ),
    ]
