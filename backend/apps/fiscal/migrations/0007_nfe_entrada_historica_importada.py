import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0006_empresa_primeiro_classificacao_participantes'),
    ]

    operations = [
        migrations.CreateModel(
            name='NFeEntradaHistoricaImportada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chave_acesso', models.CharField(db_index=True, max_length=44, unique=True)),
                ('numero', models.CharField(max_length=16)),
                ('serie', models.CharField(blank=True, max_length=4)),
                ('modelo', models.CharField(blank=True, max_length=4)),
                ('dh_emissao', models.DateTimeField()),
                ('tp_amb', models.CharField(blank=True, max_length=1)),
                ('tp_nf', models.CharField(blank=True, max_length=1)),
                ('nat_op', models.CharField(blank=True, max_length=120)),
                ('versao_layout', models.CharField(blank=True, max_length=16)),
                ('cstat', models.CharField(blank=True, max_length=8)),
                ('xmotivo', models.CharField(blank=True, max_length=255)),
                ('protocolo', models.CharField(blank=True, max_length=30)),
                ('valor_produtos', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('valor_total_nf', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('v_frete', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('v_seg', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('v_desc', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('v_outro', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14)),
                ('emit_json', models.JSONField(blank=True, default=dict)),
                ('dest_json', models.JSONField(blank=True, default=dict)),
                ('totais_json', models.JSONField(blank=True, default=dict)),
                ('reforma_e_outros_json', models.JSONField(blank=True, default=dict)),
                ('prot_json', models.JSONField(blank=True, default=dict)),
                ('papel_empresa_no_documento', models.CharField(blank=True, max_length=32)),
                ('importada', models.BooleanField(default=True)),
                ('origem_externa', models.BooleanField(default=True)),
                ('historica', models.BooleanField(default=True)),
                ('nome_arquivo', models.CharField(blank=True, max_length=255)),
                ('importado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'empresa_destinataria',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='nf_entrada_historicas_importadas_como_destinataria',
                        to='cadastros.empresa',
                    ),
                ),
                (
                    'fornecedor_emitente',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='nf_entrada_historicas_importadas_como_emitente',
                        to='cadastros.fornecedor',
                    ),
                ),
            ],
            options={
                'verbose_name': 'NF-e entrada importada (histórico)',
                'verbose_name_plural': 'NF-e entrada importadas (histórico)',
                'ordering': ['-dh_emissao', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ItemNFeEntradaHistoricaImportada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('n_item', models.PositiveIntegerField()),
                ('prod_json', models.JSONField(blank=True, default=dict)),
                ('imposto_json', models.JSONField(blank=True, default=dict)),
                (
                    'nf',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='itens',
                        to='fiscal.nfeentradahistoricaimportada',
                    ),
                ),
            ],
            options={'ordering': ['nf_id', 'n_item']},
        ),
    ]

