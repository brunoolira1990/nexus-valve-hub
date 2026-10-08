# Generated manually — inutilização SEFAZ NF-e (ERP 4.0.16.3)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0056_ordenacao_itens_inclusao'),
    ]

    operations = [
        migrations.CreateModel(
            name='NFeInutilizacaoSefaz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('serie', models.CharField(max_length=3)),
                ('ambiente', models.CharField(max_length=16)),
                ('ano', models.CharField(blank=True, max_length=2)),
                ('numero_inicial', models.PositiveIntegerField()),
                ('numero_final', models.PositiveIntegerField()),
                ('justificativa', models.TextField()),
                ('protocolo', models.CharField(blank=True, max_length=32)),
                ('cstat', models.CharField(blank=True, max_length=8)),
                ('xmotivo', models.TextField(blank=True)),
                ('xml_retorno', models.TextField(blank=True)),
                ('sefaz_ok', models.BooleanField(default=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'configuracao',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='inutilizacoes_sefaz',
                        to='fiscal.nfenumeracaoconfiguracao',
                    ),
                ),
                (
                    'criado_por',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='nfe_inutilizacoes_criadas',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Inutilização NF-e SEFAZ',
                'verbose_name_plural': 'Inutilizações NF-e SEFAZ',
                'ordering': ['-criado_em', '-pk'],
            },
        ),
        migrations.AddIndex(
            model_name='nfeinutilizacaosefaz',
            index=models.Index(
                fields=['configuracao', 'serie', 'numero_inicial', 'numero_final'],
                name='fiscal_nfe__configu_inut_idx',
            ),
        ),
        migrations.AlterField(
            model_name='nfesaidaevento',
            name='tipo_evento',
            field=models.CharField(
                choices=[
                    ('RASCUNHO_CRIADO', 'Rascunho criado'),
                    ('VALIDADA', 'Validada (pré-emissão)'),
                    ('AUTORIZACAO_EFEITOS_APLICADOS', 'Efeitos de autorização aplicados (interno)'),
                    ('CANCELAMENTO_EFEITOS_APLICADOS', 'Efeitos de cancelamento aplicados (interno)'),
                    ('CANCELADA', 'Cancelada (interno)'),
                    ('ESTORNO_FATURAMENTO', 'Estorno de faturamento vinculado'),
                    ('ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE', 'Estorno de faturamento antes da autorização SEFAZ'),
                    ('DESCARTE_RASCUNHO_NFE', 'Descarte interno de NF-e rascunho'),
                    ('NUMERACAO_LIBERADA_DESCARTE', 'Numeração liberada após descarte local'),
                    ('NUMERACAO_REUTILIZADA', 'Numeração reutilizada de descarte local'),
                    ('NUMERACAO_RECUPERADA_LOCALMENTE', 'Numeração recuperada administrativamente (local)'),
                    ('IMPOSTOS_ATUALIZADOS', 'Impostos atualizados da regra atual'),
                    ('CONFERENCIA_SALVA', 'Conferência salva'),
                    ('CONFERENCIA_VALIDADA', 'Conferência validada'),
                    ('CONFERENCIA_COM_PENDENCIAS', 'Conferência com pendências'),
                    ('PRONTA_PARA_EMISSAO', 'Pronta para emissão'),
                    ('PRONTIDAO_INVALIDADA', 'Prontidão invalidada'),
                    ('OBSERVACAO', 'Observação'),
                    ('EMISSAO_HOMOLOGACAO_INICIADA', 'Emissão homologação iniciada'),
                    ('NUMERACAO_RESERVADA', 'Numeração reservada'),
                    ('XML_OFICIAL_GERADO', 'XML oficial gerado'),
                    ('XML_ASSINADO', 'XML assinado'),
                    ('NFE_ENVIADA_HOMOLOGACAO', 'NF-e enviada homologação'),
                    ('NFE_AUTORIZADA_HOMOLOGACAO', 'NF-e autorizada homologação'),
                    ('NFE_REJEITADA_HOMOLOGACAO', 'NF-e rejeitada homologação'),
                    ('EMISSAO_PRODUCAO_INICIADA', 'Emissão produção iniciada'),
                    ('NFE_ENVIADA_PRODUCAO', 'NF-e enviada produção'),
                    ('NFE_AUTORIZADA_PRODUCAO', 'NF-e autorizada produção'),
                    ('NFE_REJEITADA_PRODUCAO', 'NF-e rejeitada produção'),
                    ('ERRO_TRANSMISSAO_SEFAZ', 'Erro transmissão SEFAZ'),
                    ('CONSULTA_SITUACAO_SEFAZ', 'Consulta situação SEFAZ'),
                    ('CARTA_CORRECAO_EMITIDA', 'Carta de Correção emitida'),
                    ('CANCELAMENTO_SEFAZ_EMITIDO', 'Cancelamento SEFAZ emitido'),
                    ('INUTILIZACAO_SEFAZ_EMITIDA', 'Inutilização SEFAZ emitida'),
                ],
                max_length=40,
            ),
        ),
    ]
