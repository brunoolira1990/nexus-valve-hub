from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('comercial', '0041_cotacaofornecedor_cotacaofornecedoritem_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='cotacaofornecedor',
            name='proposta',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cotacoes_fornecedores',
                to='comercial.proposta',
            ),
        ),
        migrations.AlterField(
            model_name='cotacaofornecedoritem',
            name='item_proposta',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cotacoes_fornecedores',
                to='comercial.itemproposta',
            ),
        ),
        migrations.AddField(
            model_name='cotacaofornecedoritem',
            name='descricao_item',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='cotacaofornecedoritem',
            name='unidade',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.CreateModel(
            name='CotacaoFornecedorHistorico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evento', models.CharField(max_length=64)),
                ('descricao', models.TextField()),
                ('dados_json', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('cotacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico', to='comercial.cotacaofornecedor')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='historico_cotacoes_fornecedores', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-criado_em', '-id']},
        ),
        migrations.RemoveConstraint(
            model_name='cotacaofornecedoritem',
            name='uniq_cotacao_item_proposta',
        ),
        migrations.AddConstraint(
            model_name='cotacaofornecedoritem',
            constraint=models.UniqueConstraint(
                condition=models.Q(('item_proposta__isnull', False)),
                fields=('cotacao', 'item_proposta'),
                name='uniq_cotacao_item_proposta',
            ),
        ),
        migrations.AddConstraint(
            model_name='cotacaofornecedoritem',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(('item_proposta__isnull', False))
                    | (
                        models.Q(('descricao_item__gt', ''))
                        & models.Q(('unidade__gt', ''))
                        & models.Q(('quantidade__gt', Decimal('0')))
                    )
                ),
                name='cot_item_manual_estrutura_valida',
            ),
        ),
    ]
