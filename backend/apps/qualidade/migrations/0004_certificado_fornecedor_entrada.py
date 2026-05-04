# Certificado de fornecedor / entrada para reaproveitar dados técnicos

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0009_cte_reconhecer_empresa_tomadora'),
        ('qualidade', '0003_componentes_valvula'),
        ('produtos', '0005_familia_variacoes_permitidas'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificadoFornecedorEntrada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_certificado_fornecedor', models.CharField(blank=True, max_length=64)),
                ('fornecedor_nome_snapshot', models.CharField(blank=True, max_length=255)),
                ('fornecedor_cnpj_snapshot', models.CharField(blank=True, max_length=32)),
                ('numero_nf_entrada', models.CharField(blank=True, max_length=64)),
                ('serie_nf_entrada', models.CharField(blank=True, max_length=16)),
                ('data_nf_entrada', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('rascunho', 'Rascunho'), ('registrado', 'Registrado'), ('cancelado', 'Cancelado')], default='rascunho', max_length=16)),
                ('observacoes', models.TextField(blank=True)),
                ('arquivo_original', models.FileField(blank=True, null=True, upload_to='certificados_fornecedor/%Y/%m/')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('empresa_destinataria', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_fornecedor_recebidos', to='cadastros.empresa')),
                ('fornecedor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_fornecedor_entrada', to='cadastros.fornecedor')),
                ('nf_entrada_historica', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_fornecedor', to='fiscal.nfeentradahistoricaimportada')),
                ('nf_entrada_operacional', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificados_fornecedor', to='fiscal.nfeentrada')),
            ],
            options={'ordering': ['-criado_em']},
        ),
        migrations.CreateModel(
            name='ItemCertificadoFornecedorEntrada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(default=1)),
                ('codigo_produto', models.CharField(blank=True, max_length=128)),
                ('descricao_material', models.CharField(blank=True, max_length=512)),
                ('quantidade', models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ('unidade', models.CharField(blank=True, max_length=16)),
                ('ncm', models.CharField(blank=True, max_length=16)),
                ('norma', models.CharField(blank=True, max_length=128)),
                ('corrida', models.CharField(blank=True, max_length=64)),
                ('lote', models.CharField(blank=True, max_length=64)),
                ('tipo_dados_tecnicos', models.CharField(choices=[('PADRAO_ITEM', 'Dados por item'), ('VALVULA_COMPONENTES', 'Dados por componentes de válvula')], default='PADRAO_ITEM', max_length=32)),
                ('composicao_json', models.JSONField(blank=True, default=dict)),
                ('ensaio_tracao_json', models.JSONField(blank=True, default=dict)),
                ('ensaio_impacto_json', models.JSONField(blank=True, default=dict)),
                ('observacoes_item', models.TextField(blank=True)),
                ('ativo', models.BooleanField(default=True)),
                ('certificado_fornecedor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='qualidade.certificadofornecedorentrada')),
                ('produto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='itens_certificado_fornecedor_entrada', to='produtos.produto')),
            ],
            options={'ordering': ['ordem', 'id']},
        ),
        migrations.CreateModel(
            name='ComponenteCertificadoFornecedorEntrada',
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
                ('item_certificado_fornecedor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='componentes', to='qualidade.itemcertificadofornecedorentrada')),
            ],
            options={'ordering': ['ordem', 'id']},
        ),
    ]
