# Generated manually — Sprint 1 Cenário Fiscal de Entrada

import django.db.models.deletion
from django.db import migrations, models


def migrar_regras_para_cenario_padrao(apps, schema_editor):
    CenarioFiscalEntrada = apps.get_model('regras_fiscais', 'CenarioFiscalEntrada')
    CenarioFiscalEntradaEscopo = apps.get_model('regras_fiscais', 'CenarioFiscalEntradaEscopo')
    RegraFiscalEntrada = apps.get_model('regras_fiscais', 'RegraFiscalEntrada')

    cenario, _ = CenarioFiscalEntrada.objects.get_or_create(
        padrao=True,
        defaults={
            'nome': 'Cenário Padrão',
            'ativo': True,
            'observacoes': 'Cenário criado automaticamente para regras de entrada existentes.',
        },
    )
    if not cenario.ativo:
        cenario.ativo = True
        cenario.save(update_fields=['ativo'])

    escopos_cache: dict[tuple, int] = {}

    def escopo_id_para_regra(regra) -> int:
        if regra.produto_id:
            chave = ('PRODUTO', '', regra.produto_id)
        else:
            ncm = (regra.ncm or '').strip()
            if ncm and regra.ncm_prefixo:
                chave = ('NCM_PREFIXO', ncm, None)
            elif ncm:
                chave = ('NCM', ncm, None)
            else:
                chave = ('GERAL', '', None)

        if chave in escopos_cache:
            return escopos_cache[chave]

        tipo, ncm_val, produto_id = chave
        escopo, _ = CenarioFiscalEntradaEscopo.objects.get_or_create(
            cenario_id=cenario.id,
            tipo_escopo=tipo,
            ncm=ncm_val,
            produto_id=produto_id,
            defaults={'ativo': True, 'prioridade_escopo': 10},
        )
        escopos_cache[chave] = escopo.id
        return escopo.id

    def label_folha(regra, escopo_id):
        escopo = CenarioFiscalEntradaEscopo.objects.filter(pk=escopo_id).first()
        if escopo.tipo_escopo == 'GERAL':
            escopo_label = 'Regra geral'
        elif escopo.tipo_escopo == 'PRODUTO':
            escopo_label = f'Produto {escopo.produto_id or 0}'
        elif escopo.tipo_escopo == 'NCM_PREFIXO':
            escopo_label = f'NCM {(escopo.ncm or "").strip()} (prefixo)'
        else:
            escopo_label = f'NCM {(escopo.ncm or "").strip()}'
        ufo = (regra.uf_origem or '').strip().upper()[:2] or '*'
        ufd = (regra.uf_destino or '').strip().upper()[:2] or '*'
        cfop_o = ''.join(c for c in (regra.cfop_origem or regra.cfop or '') if c.isdigit()) or '?'
        cfop_e = ''.join(c for c in (regra.cfop_entrada or '') if c.isdigit()) or '?'
        return f'{escopo_label} · {ufo}→{ufd} · {cfop_o}→{cfop_e}'

    for regra in RegraFiscalEntrada.objects.iterator():
        eid = escopo_id_para_regra(regra)
        rotulo = label_folha(regra, eid)[:255]
        nome = (regra.nome or '').strip() or rotulo[:120]
        RegraFiscalEntrada.objects.filter(pk=regra.pk).update(
            cenario_id=cenario.id,
            escopo_id=eid,
            descricao_cenario=rotulo,
            nome=nome[:120],
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0009_alter_cliente_dias_parcelas_and_more'),
        ('produtos', '0021_alter_familia_tipo_dimensional_regra_pvc_pu'),
        ('regras_fiscais', '0005_regra_fiscal_entrada_impostos_detalhados'),
    ]

    operations = [
        migrations.CreateModel(
            name='CenarioFiscalEntrada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('regime_tributario', models.CharField(blank=True, max_length=64)),
                ('ativo', models.BooleanField(default=True)),
                ('padrao', models.BooleanField(default=False, help_text='Cenário usado na conferência quando nenhum outro é informado.')),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'empresa',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='cenarios_fiscais_entrada',
                        to='cadastros.empresa',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Cenário fiscal de entrada',
                'verbose_name_plural': 'Cenários fiscais de entrada',
                'ordering': ['-padrao', 'nome', 'id'],
            },
        ),
        migrations.CreateModel(
            name='CenarioFiscalEntradaEscopo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_escopo', models.CharField(choices=[('GERAL', 'Regra geral'), ('NCM', 'NCM'), ('NCM_PREFIXO', 'NCM por prefixo'), ('PRODUTO', 'Produto específico')], max_length=16)),
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
                        to='regras_fiscais.cenariofiscalentrada',
                    ),
                ),
                (
                    'produto',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='escopos_fiscais_entrada',
                        to='produtos.produto',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Escopo do cenário fiscal de entrada',
                'verbose_name_plural': 'Escopos do cenário fiscal de entrada',
                'ordering': ['tipo_escopo', 'ncm', 'produto_id', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='cenariofiscalentradaescopo',
            constraint=models.UniqueConstraint(
                fields=('cenario', 'tipo_escopo', 'ncm', 'produto'),
                name='uniq_cenario_fiscal_entrada_escopo',
            ),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='cenario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='configuracoes',
                to='regras_fiscais.cenariofiscalentrada',
            ),
        ),
        migrations.AddField(
            model_name='regrafiscalentrada',
            name='escopo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='configuracoes',
                to='regras_fiscais.cenariofiscalentradaescopo',
            ),
        ),
        migrations.AddIndex(
            model_name='regrafiscalentrada',
            index=models.Index(fields=['cenario', 'escopo', 'ativo'], name='regras_fisc_cenario_8a1f2d_idx'),
        ),
        migrations.RunPython(migrar_regras_para_cenario_padrao, noop_reverse),
    ]
