from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cadastros', '0017_alter_transportadora_cnpj'),
        ('comercial', '0041_proposta_rentabilidade_canonica'),
        ('produtos', '0027_familia_codigo_sequencia'),
    ]

    operations = [
        migrations.CreateModel(
            name='CotacaoFornecedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=32, unique=True)),
                ('data', models.DateField()),
                ('prazo_resposta', models.DateField(blank=True, null=True)),
                ('observacao', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('RASCUNHO', 'Rascunho'), ('EM_COTACAO', 'Em cotação'), ('PARCIAL', 'Parcial'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], db_index=True, default='RASCUNHO', max_length=16)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('proposta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cotacoes_fornecedores', to='comercial.proposta')),
                ('responsavel', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cotacoes_fornecedores_responsavel', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-data', '-id'], 'permissions': (('registrar_resposta_cotacaofornecedor', 'Pode registrar resposta de cotação com fornecedor'), ('selecionar_referencia_cotacaofornecedor', 'Pode selecionar referência de cotação com fornecedor'), ('cancel_cotacaofornecedor', 'Pode cancelar cotação com fornecedor'))},
        ),
        migrations.CreateModel(
            name='CotacaoFornecedorItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('produto_snapshot', models.JSONField(blank=True, default=dict)),
                ('quantidade', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('observacao_tecnica', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('PARCIAL', 'Parcial'), ('COTADO', 'Cotado'), ('CANCELADO', 'Cancelado')], default='PENDENTE', max_length=16)),
                ('cotacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='comercial.cotacaofornecedor')),
                ('item_proposta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cotacoes_fornecedores', to='comercial.itemproposta')),
                ('produto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='produtos.produto')),
            ],
            options={'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='CotacaoFornecedorParticipante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('RESPONDIDO', 'Respondido'), ('RECUSADO', 'Recusado'), ('SEM_RETORNO', 'Sem retorno')], default='PENDENTE', max_length=16)),
                ('enviado_em', models.DateTimeField(blank=True, null=True)),
                ('respondido_em', models.DateTimeField(blank=True, null=True)),
                ('observacao', models.TextField(blank=True)),
                ('cotacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participantes', to='comercial.cotacaofornecedor')),
                ('fornecedor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='cotacoes_fornecedores', to='cadastros.fornecedor')),
            ],
            options={'ordering': ['fornecedor__razao_social', 'id']},
        ),
        migrations.CreateModel(
            name='CotacaoFornecedorRespostaItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('preco_unitario', models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True)),
                ('quantidade_atendida', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('prazo_entrega', models.CharField(blank=True, max_length=120)),
                ('condicao_pagamento', models.CharField(blank=True, max_length=120)),
                ('frete', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('frete_tipo', models.CharField(blank=True, max_length=24)),
                ('marca_fabricante', models.CharField(blank=True, max_length=255)),
                ('validade', models.DateField(blank=True, null=True)),
                ('observacao', models.TextField(blank=True)),
                ('status_item', models.CharField(choices=[('RESPONDIDO', 'Respondido'), ('RECUSADO', 'Recusado'), ('SEM_RETORNO', 'Sem retorno')], default='RESPONDIDO', max_length=16)),
                ('selecionada_como_referencia', models.BooleanField(db_index=True, default=False)),
                ('selecionada_em', models.DateTimeField(blank=True, null=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('cotacao_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='respostas', to='comercial.cotacaofornecedoritem')),
                ('participante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='respostas', to='comercial.cotacaofornecedorparticipante')),
                ('selecionada_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='respostas_cotacao_selecionadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['id']},
        ),
        migrations.AddConstraint(model_name='cotacaofornecedoritem', constraint=models.UniqueConstraint(fields=('cotacao', 'item_proposta'), name='uniq_cotacao_item_proposta')),
        migrations.AddConstraint(model_name='cotacaofornecedoritem', constraint=models.CheckConstraint(condition=models.Q(('quantidade__gte', Decimal('0'))), name='cot_item_quantidade_nao_neg')),
        migrations.AddConstraint(model_name='cotacaofornecedorparticipante', constraint=models.UniqueConstraint(fields=('cotacao', 'fornecedor'), name='uniq_cotacao_fornecedor_participante')),
        migrations.AddConstraint(model_name='cotacaofornecedorrespostaitem', constraint=models.UniqueConstraint(fields=('participante', 'cotacao_item'), name='uniq_cotacao_resposta_participante_item')),
        migrations.AddConstraint(model_name='cotacaofornecedorrespostaitem', constraint=models.CheckConstraint(condition=models.Q(('preco_unitario__isnull', True)) | models.Q(('preco_unitario__gte', Decimal('0'))), name='cot_resp_preco_nao_neg')),
        migrations.AddConstraint(model_name='cotacaofornecedorrespostaitem', constraint=models.CheckConstraint(condition=models.Q(('quantidade_atendida__gte', Decimal('0'))), name='cot_resp_qtd_atendida_nao_neg')),
        migrations.AddConstraint(model_name='cotacaofornecedorrespostaitem', constraint=models.CheckConstraint(condition=models.Q(('frete__isnull', True)) | models.Q(('frete__gte', Decimal('0'))), name='cot_resp_frete_nao_neg')),
    ]
