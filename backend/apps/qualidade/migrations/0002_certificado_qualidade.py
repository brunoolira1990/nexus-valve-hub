# Certificado de Qualidade por NF-e (MVP)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0009_cte_reconhecer_empresa_tomadora'),
        ('qualidade', '0001_initial'),
        ('cadastros', '0001_initial'),
        ('produtos', '0005_familia_variacoes_permitidas'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificadoQualidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=32)),
                ('serie', models.CharField(blank=True, max_length=16)),
                ('cliente_nome_snapshot', models.CharField(blank=True, max_length=255)),
                ('cliente_cnpj_snapshot', models.CharField(blank=True, max_length=32)),
                ('pedido_cliente', models.CharField(blank=True, max_length=120)),
                ('nota_fiscal_numero', models.CharField(blank=True, max_length=64)),
                ('data_emissao', models.DateField(blank=True, null=True)),
                ('observacoes', models.TextField(blank=True)),
                ('texto_padrao', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('rascunho', 'Rascunho'), ('emitido', 'Emitido'), ('cancelado', 'Cancelado')], default='rascunho', max_length=16)),
                ('tipo_certificado', models.CharField(choices=[('PADRAO_POR_NFE', 'Padrão por NF-e'), ('VALVULA_COMPONENTES', 'Válvula por componentes')], default='PADRAO_POR_NFE', max_length=32)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_qualidade', to='cadastros.cliente')),
                ('nota_fiscal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_qualidade', to='fiscal.nfesaida')),
                ('nota_fiscal_historica', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_qualidade', to='fiscal.nfesaidahistoricaimportada')),
            ],
            options={
                'ordering': ['-criado_em'],
                'constraints': [models.UniqueConstraint(fields=('numero', 'serie'), name='uq_certificado_qualidade_numero_serie')],
            },
        ),
        migrations.CreateModel(
            name='ItemCertificadoQualidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(default=1)),
                ('codigo_produto', models.CharField(blank=True, max_length=128)),
                ('descricao_material', models.CharField(blank=True, max_length=512)),
                ('quantidade', models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ('unidade', models.CharField(blank=True, max_length=16)),
                ('norma', models.CharField(blank=True, max_length=128)),
                ('corrida', models.CharField(blank=True, max_length=64)),
                ('ncm', models.CharField(blank=True, max_length=16)),
                ('observacoes_item', models.TextField(blank=True)),
                ('composicao_json', models.JSONField(blank=True, default=dict)),
                ('ensaio_tracao_json', models.JSONField(blank=True, default=dict)),
                ('ensaio_impacto_json', models.JSONField(blank=True, default=dict)),
                ('certificado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='qualidade.certificadoqualidade')),
                ('produto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_certificado_qualidade', to='produtos.produto')),
            ],
            options={
                'ordering': ['ordem', 'id'],
            },
        ),
    ]
