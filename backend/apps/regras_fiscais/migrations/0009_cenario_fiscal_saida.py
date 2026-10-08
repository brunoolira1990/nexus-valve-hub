# Cenário Fiscal de Saída — modelos base e cenário padrão

import django.db.models.deletion
from django.db import migrations, models


def criar_cenario_padrao_saida(apps, schema_editor):
    CenarioFiscalSaida = apps.get_model('regras_fiscais', 'CenarioFiscalSaida')
    CenarioFiscalSaida.objects.get_or_create(
        padrao=True,
        defaults={
            'nome': 'Cenário Padrão de Saída',
            'ativo': True,
            'observacoes': 'Cenário criado automaticamente para configurações fiscais de saída.',
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0001_initial'),
        ('produtos', '0001_initial'),
        ('regras_fiscais', '0008_regra_fiscal_entrada_fcp_reforma'),
    ]

    operations = [
        migrations.CreateModel(
            name='CenarioFiscalSaida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('regime_tributario', models.CharField(blank=True, max_length=64)),
                ('ativo', models.BooleanField(default=True)),
                (
                    'padrao',
                    models.BooleanField(
                        default=False,
                        help_text='Cenário usado por padrão quando nenhum outro for informado.',
                    ),
                ),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'empresa',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='cenarios_fiscais_saida',
                        to='cadastros.empresa',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Cenário fiscal de saída',
                'verbose_name_plural': 'Cenários fiscais de saída',
                'ordering': ['-padrao', 'nome', 'id'],
            },
        ),
        migrations.CreateModel(
            name='CenarioFiscalSaidaEscopo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'tipo_escopo',
                    models.CharField(
                        choices=[
                            ('GERAL', 'Regra geral'),
                            ('NCM', 'NCM'),
                            ('NCM_PREFIXO', 'NCM por prefixo'),
                            ('PRODUTO', 'Produto específico'),
                        ],
                        max_length=16,
                    ),
                ),
                ('ncm', models.CharField(blank=True, max_length=16)),
                ('prioridade_escopo', models.IntegerField(default=10)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'cenario',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='escopos',
                        to='regras_fiscais.cenariofiscalsaida',
                    ),
                ),
                (
                    'produto',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='escopos_fiscais_saida',
                        to='produtos.produto',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Escopo do cenário fiscal de saída',
                'verbose_name_plural': 'Escopos do cenário fiscal de saída',
                'ordering': ['tipo_escopo', 'ncm', 'produto_id', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RegraFiscalSaida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(blank=True, max_length=120)),
                ('codigo', models.CharField(blank=True, max_length=32)),
                ('ativo', models.BooleanField(default=True)),
                ('prioridade', models.IntegerField(default=0)),
                ('uf_origem', models.CharField(blank=True, max_length=2)),
                ('uf_destino', models.CharField(blank=True, max_length=2)),
                (
                    'destinatario_contribuinte',
                    models.CharField(
                        choices=[
                            ('CONTRIBUINTE', 'Contribuinte'),
                            ('NAO_CONTRIBUINTE', 'Não contribuinte'),
                            ('QUALQUER', 'Qualquer'),
                        ],
                        default='QUALQUER',
                        max_length=20,
                    ),
                ),
                ('consumidor_final', models.BooleanField(blank=True, null=True)),
                ('cfop_venda', models.CharField(blank=True, max_length=8)),
                ('cfop_venda_st', models.CharField(blank=True, max_length=8)),
                (
                    'tipo_operacao',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('VENDA', 'Venda'),
                            ('DEVOLUCAO', 'Devolução'),
                            ('REMESSA', 'Remessa'),
                            ('BONIFICACAO', 'Bonificação'),
                            ('INDUSTRIALIZACAO', 'Industrialização'),
                            ('OUTROS', 'Outros'),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    'descricao_cenario',
                    models.CharField(
                        blank=True,
                        help_text='Rótulo da configuração (gerado automaticamente).',
                        max_length=255,
                    ),
                ),
                ('cst_icms', models.CharField(blank=True, max_length=8)),
                ('csosn', models.CharField(blank=True, max_length=8)),
                ('modalidade_bc_icms', models.CharField(blank=True, max_length=8)),
                ('aliquota_icms', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('reducao_bc_icms', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('motivo_desoneracao_icms', models.CharField(blank=True, max_length=8)),
                ('codigo_beneficio_icms', models.CharField(blank=True, max_length=16)),
                ('icms_st_aplicavel', models.BooleanField(blank=True, null=True)),
                ('cst_icms_st', models.CharField(blank=True, max_length=8)),
                ('aliquota_icms_st', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('mva_st', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('reducao_bc_st', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('fcp_aplicavel', models.BooleanField(blank=True, null=True)),
                ('aliquota_fcp', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('aliquota_fcp_st', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('reducao_bc_fcp', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('valor_fcp_unidade', models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ('reforma_tributaria', models.JSONField(blank=True, null=True)),
                ('cst_ipi', models.CharField(blank=True, max_length=8)),
                ('tipo_calculo_ipi', models.CharField(blank=True, max_length=8)),
                ('aliquota_ipi', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('valor_ipi_unidade', models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ('enquadramento_ipi', models.CharField(blank=True, max_length=8)),
                ('cst_pis', models.CharField(blank=True, max_length=8)),
                ('tipo_calculo_pis', models.CharField(blank=True, max_length=8)),
                ('aliquota_pis', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('reducao_base_pis', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('valor_minimo_pis_unidade', models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ('aliquota_pis_st', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('cst_cofins', models.CharField(blank=True, max_length=8)),
                ('tipo_calculo_cofins', models.CharField(blank=True, max_length=8)),
                ('aliquota_cofins', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('reducao_base_cofins', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('valor_minimo_cofins_unidade', models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ('aliquota_cofins_st', models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True)),
                ('movimenta_estoque', models.BooleanField(default=True)),
                ('gera_financeiro', models.BooleanField(default=True)),
                ('informacoes_complementares', models.TextField(blank=True)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'cenario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='configuracoes',
                        to='regras_fiscais.cenariofiscalsaida',
                    ),
                ),
                (
                    'escopo',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='configuracoes',
                        to='regras_fiscais.cenariofiscalsaidaescopo',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Regra fiscal de saída',
                'verbose_name_plural': 'Regras fiscais de saída',
                'ordering': ['-prioridade', 'nome', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='cenariofiscalsaidaescopo',
            constraint=models.UniqueConstraint(
                fields=('cenario', 'tipo_escopo', 'ncm', 'produto'),
                name='uniq_cenario_fiscal_saida_escopo',
            ),
        ),
        migrations.AddIndex(
            model_name='regrafiscalsaida',
            index=models.Index(fields=['ativo', '-prioridade'], name='regras_fisc_ativo_p_saida_idx'),
        ),
        migrations.AddIndex(
            model_name='regrafiscalsaida',
            index=models.Index(fields=['cfop_venda'], name='regras_fisc_cfop_v_saida_idx'),
        ),
        migrations.AddIndex(
            model_name='regrafiscalsaida',
            index=models.Index(fields=['cenario', 'escopo', 'ativo'], name='regras_fisc_cen_esc_saida_idx'),
        ),
        migrations.RunPython(criar_cenario_padrao_saida, noop_reverse),
    ]
