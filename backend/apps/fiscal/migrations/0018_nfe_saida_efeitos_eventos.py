# Generated manually — NF-e Saída 3.1 política de efeitos

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comercial', '0026_vendedor_colaborador_fk'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0017_itemnfesaida_item_faturamento_pedido_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='cancelada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='cancelada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_saidas_canceladas',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='efeitos_autorizacao_aplicados_em',
            field=models.DateTimeField(
                blank=True,
                help_text='Quando os efeitos operacionais de autorização (interna) foram aplicados.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='efeitos_cancelamento_aplicados_em',
            field=models.DateTimeField(
                blank=True,
                help_text='Quando os efeitos operacionais de cancelamento (interno) foram aplicados.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='efeitos_cancelamento_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_saidas_cancelamento_efeitos',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='motivo_cancelamento',
            field=models.TextField(
                blank=True,
                help_text='Motivo do cancelamento interno (simulação pré-SEFAZ).',
            ),
        ),
        migrations.CreateModel(
            name='NFeSaidaEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_evento', models.CharField(choices=[
                    ('RASCUNHO_CRIADO', 'Rascunho criado'),
                    ('VALIDADA', 'Validada (pré-emissão)'),
                    ('AUTORIZACAO_EFEITOS_APLICADOS', 'Efeitos de autorização aplicados (interno)'),
                    ('CANCELAMENTO_EFEITOS_APLICADOS', 'Efeitos de cancelamento aplicados (interno)'),
                    ('CANCELADA', 'Cancelada (interno)'),
                    ('ESTORNO_FATURAMENTO', 'Estorno de faturamento vinculado'),
                    ('OBSERVACAO', 'Observação'),
                ], max_length=40)),
                ('status_anterior', models.CharField(blank=True, max_length=64)),
                ('status_novo', models.CharField(blank=True, max_length=64)),
                ('resumo', models.JSONField(blank=True, null=True)),
                ('observacao', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('criado_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_nfe_saida_criados',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('faturamento_pedido_venda', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_nfe_saida',
                    to='comercial.faturamentopedidovenda',
                )),
                ('nfe_saida', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='eventos',
                    to='fiscal.nfesaida',
                )),
                ('pedido_venda', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_nfe_saida',
                    to='comercial.pedidovenda',
                )),
            ],
            options={
                'ordering': ['-criado_em', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='nfesaidaevento',
            index=models.Index(fields=['nfe_saida', '-criado_em'], name='fiscal_nfes_nfe_sai_criado_idx'),
        ),
    ]
