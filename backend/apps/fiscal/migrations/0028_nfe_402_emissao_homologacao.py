# Generated manually — NF-e 4.0.2 emissão homologação

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_numeracao_homolog_producao(apps, schema_editor):
    Empresa = apps.get_model('cadastros', 'Empresa')
    NFeNumeracaoConfiguracao = apps.get_model('fiscal', 'NFeNumeracaoConfiguracao')
    for emp in Empresa.objects.all():
        NFeNumeracaoConfiguracao.objects.get_or_create(
            empresa_id=emp.pk,
            modelo_documento='55',
            ambiente='homologacao',
            serie='900',
            defaults={'proximo_numero': 2, 'ativo': True},
        )
        NFeNumeracaoConfiguracao.objects.get_or_create(
            empresa_id=emp.pk,
            modelo_documento='55',
            ambiente='producao',
            serie='1',
            defaults={'proximo_numero': 1, 'ativo': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0011_cliente_informacoes_complementares_nfe'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0027_alter_nfesaida_chave_acesso_preliminar_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='NFeNumeracaoConfiguracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modelo_documento', models.CharField(default='55', max_length=2)),
                ('ambiente', models.CharField(choices=[('homologacao', 'Homologação'), ('producao', 'Produção')], max_length=16)),
                ('serie', models.CharField(default='900', max_length=3)),
                ('proximo_numero', models.PositiveIntegerField(default=1)),
                ('ultimo_numero_reservado', models.PositiveIntegerField(blank=True, null=True)),
                ('ultimo_numero_autorizado', models.PositiveIntegerField(blank=True, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='numeracoes_nfe', to='cadastros.empresa')),
            ],
            options={
                'verbose_name': 'Configuração numeração NF-e',
                'verbose_name_plural': 'Configurações numeração NF-e',
                'ordering': ['empresa_id', 'ambiente', 'serie'],
            },
        ),
        migrations.AddConstraint(
            model_name='nfenumeracaoconfiguracao',
            constraint=models.UniqueConstraint(condition=models.Q(('ativo', True)), fields=('empresa', 'modelo_documento', 'ambiente', 'serie'), name='uniq_nfe_numeracao_ativa_empresa_ambiente_serie'),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='ambiente_emissao',
            field=models.CharField(blank=True, choices=[('homologacao', 'Homologação'), ('producao', 'Produção')], max_length=16),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='autorizada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='chave_acesso',
            field=models.CharField(blank=True, db_index=True, max_length=44),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='codigo_numerico',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='cstat_autorizacao',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='digito_verificador',
            field=models.CharField(blank=True, max_length=1),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='empresa_emitente',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='nf_saidas_emitidas', to='cadastros.empresa'),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='motivo_autorizacao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='numero_nfe',
            field=models.CharField(blank=True, help_text='Número fiscal (nNF) — numérico, distinto do número interno.', max_length=9),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='numero_reservado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='numero_reservado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='nf_saidas_numeracao_reservada', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='protocolo_autorizacao',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='serie_nfe',
            field=models.CharField(blank=True, max_length=3),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='status_emissao_sefaz',
            field=models.CharField(blank=True, choices=[('NUMERACAO_RESERVADA', 'Numeração reservada'), ('XML_GERADO', 'XML oficial gerado'), ('XML_ASSINADO', 'XML assinado'), ('ENVIADA_HOMOLOGACAO', 'Enviada homologação'), ('AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'), ('REJEITADA_HOMOLOGACAO', 'Rejeitada homologação'), ('ERRO_TRANSMISSAO', 'Erro transmissão')], max_length=32),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_assinado',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_autorizado',
            field=models.TextField(blank=True, help_text='procNFe / XML autorizado com protocolo SEFAZ.'),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_envio',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_retorno',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='nfesaidaevento',
            name='tipo_evento',
            field=models.CharField(choices=[('RASCUNHO_CRIADO', 'Rascunho criado'), ('VALIDADA', 'Validada (pré-emissão)'), ('AUTORIZACAO_EFEITOS_APLICADOS', 'Efeitos de autorização aplicados (interno)'), ('CANCELAMENTO_EFEITOS_APLICADOS', 'Efeitos de cancelamento aplicados (interno)'), ('CANCELADA', 'Cancelada (interno)'), ('ESTORNO_FATURAMENTO', 'Estorno de faturamento vinculado'), ('IMPOSTOS_ATUALIZADOS', 'Impostos atualizados da regra atual'), ('CONFERENCIA_SALVA', 'Conferência salva'), ('CONFERENCIA_VALIDADA', 'Conferência validada'), ('CONFERENCIA_COM_PENDENCIAS', 'Conferência com pendências'), ('PRONTA_PARA_EMISSAO', 'Pronta para emissão'), ('PRONTIDAO_INVALIDADA', 'Prontidão invalidada'), ('OBSERVACAO', 'Observação'), ('NUMERACAO_RESERVADA', 'Numeração reservada'), ('XML_OFICIAL_GERADO', 'XML oficial gerado'), ('XML_ASSINADO', 'XML assinado'), ('NFE_ENVIADA_HOMOLOGACAO', 'NF-e enviada homologação'), ('NFE_AUTORIZADA_HOMOLOGACAO', 'NF-e autorizada homologação'), ('NFE_REJEITADA_HOMOLOGACAO', 'NF-e rejeitada homologação'), ('ERRO_TRANSMISSAO_SEFAZ', 'Erro transmissão SEFAZ')], max_length=40),
        ),
        migrations.RunPython(seed_numeracao_homolog_producao, migrations.RunPython.noop),
    ]
