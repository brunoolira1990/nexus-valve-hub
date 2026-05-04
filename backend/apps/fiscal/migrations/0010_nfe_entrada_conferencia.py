from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('comercial', '0001_initial'),
        ('fiscal', '0009_cte_reconhecer_empresa_tomadora'),
        ('produtos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NFeEntradaConferencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('CONFERIDA', 'Conferida'), ('PREPARADA', 'Entrada preparada'), ('CANCELADA', 'Cancelada/Revertida')], default='PENDENTE', max_length=16)),
                ('divergencias_aceitas', models.BooleanField(default=False)),
                ('observacao_divergencias', models.TextField(blank=True)),
                ('preparado_em', models.DateTimeField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('nf_entrada_historica', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='conferencia', to='fiscal.nfeentradahistoricaimportada')),
                ('pedido_compra', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conferencias_nf_entrada', to='comercial.pedidocompra')),
            ],
            options={'ordering': ['-atualizado_em', '-id']},
        ),
        migrations.CreateModel(
            name='ItemNFeEntradaConferencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDENTE_PRODUTO', 'Pendente produto'), ('PRODUTO_VINCULADO', 'Produto vinculado'), ('CONFERIDO', 'Conferido'), ('DIVERGENTE', 'Divergente'), ('IGNORADO', 'Ignorado')], default='PENDENTE_PRODUTO', max_length=24)),
                ('motivo_ignorado', models.CharField(blank=True, max_length=255)),
                ('observacao', models.TextField(blank=True)),
                ('corrida', models.CharField(blank=True, max_length=64)),
                ('lote', models.CharField(blank=True, max_length=64)),
                ('rastreabilidade_observacao', models.CharField(blank=True, max_length=255)),
                ('unidade_nf', models.CharField(blank=True, max_length=16)),
                ('quantidade_nf', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('valor_unitario_nf', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=14)),
                ('valor_total_nf', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('unidade_estoque_calculada', models.CharField(blank=True, max_length=16)),
                ('quantidade_estoque_calculada', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('peso_total_kg', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('metros_total', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('barras_total', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('toneladas_total', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=14)),
                ('divergencias', models.JSONField(blank=True, default=list)),
                ('alertas', models.JSONField(blank=True, default=list)),
                ('snapshot_produto', models.JSONField(blank=True, default=dict)),
                ('snapshot_pedido', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('conferencia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='fiscal.nfeentradaconferencia')),
                ('item_nfe_historico', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='item_conferencia', to='fiscal.itemnfeentradahistoricaimportada')),
                ('item_pedido_compra', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_conferencia_nfe_entrada', to='comercial.itempedidocompra')),
                ('produto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_conferencia_nfe_entrada', to='produtos.produto')),
            ],
            options={'ordering': ['item_nfe_historico__n_item']},
        ),
    ]
