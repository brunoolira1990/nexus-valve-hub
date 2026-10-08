# Generated manually for Contingência SEFAZ (NF-e).

from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0072_cte_situacao_financeira_frete'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='tipo_emissao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('1', 'Emissão normal'),
                    ('2', 'EPEC — Contingência'),
                    ('6', 'SVC-RS — Contingência'),
                    ('7', 'SVC-AN — Contingência'),
                ],
                default='1',
                help_text='tpEmis do XML oficial: 1 normal, 2 EPEC, 6 SVC-RS, 7 SVC-AN.',
                max_length=1,
            ),
        ),
        migrations.CreateModel(
            name='ContingenciaSefaz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tp_emis', models.CharField(
                    choices=[
                        ('1', 'Normal'),
                        ('2', 'EPEC'),
                        ('6', 'SVC-RS'),
                        ('7', 'SVC-AN'),
                    ],
                    max_length=1,
                )),
                ('motivo', models.TextField(blank=True, max_length=500)),
                ('inicio', models.DateTimeField()),
                ('encerrada_em', models.DateTimeField(blank=True, null=True)),
                ('ativa', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('criado_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='contingencias_sefaz_criadas',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('empresa', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='contingencias_sefaz',
                    to='cadastros.empresa',
                )),
            ],
            options={
                'verbose_name': 'Contingência SEFAZ',
                'verbose_name_plural': 'Contingências SEFAZ',
                'ordering': ['-inicio'],
            },
        ),
    ]
