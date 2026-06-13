# ERP 4.0.15.0 — Entrada Própria 1 Parte 2A: fundação backend e numeração separada

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fiscal', '0041_nfentrada_entrada_propria_importada_4014'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='nfenumeracaoconfiguracao',
            name='uniq_nfe_numeracao_ativa_empresa_ambiente_serie',
        ),
        migrations.AddField(
            model_name='nfenumeracaoconfiguracao',
            name='tipo_operacao',
            field=models.CharField(
                choices=[('saida', 'Saída'), ('entrada_propria', 'Entrada própria')],
                default='saida',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='nfenumeracaoconfiguracao',
            constraint=models.UniqueConstraint(
                condition=models.Q(('ativo', True)),
                fields=('empresa', 'modelo_documento', 'ambiente', 'tipo_operacao', 'serie'),
                name='uniq_nfe_numeracao_ativa_empresa_ambiente_tipo_serie',
            ),
        ),
        migrations.AlterField(
            model_name='nfeentrada',
            name='tipo_origem',
            field=models.CharField(
                choices=[
                    ('MANUAL', 'Manual'),
                    ('ENTRADA_PROPRIA_IMPORTADA', 'Entrada própria importada'),
                    ('ENTRADA_PROPRIA_EMITIDA', 'Entrada própria emitida'),
                ],
                default='MANUAL',
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='nfeentrada',
            name='status_operacional',
            field=models.CharField(
                choices=[
                    ('RASCUNHO', 'Rascunho'),
                    ('EM_CONFERENCIA', 'Em conferência'),
                    ('PRONTA_HOMOLOGACAO', 'Pronta homologação'),
                    ('AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'),
                    ('REJEITADA', 'Rejeitada'),
                    ('ERRO_TRANSMISSAO', 'Erro transmissão'),
                    ('IMPORTADA_PENDENTE_CONFERENCIA', 'Importada — pendente conferência'),
                ],
                default='RASCUNHO',
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='ambiente_emissao',
            field=models.CharField(
                blank=True,
                choices=[('homologacao', 'Homologação'), ('producao', 'Produção')],
                default='homologacao',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='fin_nfe',
            field=models.CharField(blank=True, max_length=1),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='chave_nfe_referenciada',
            field=models.CharField(blank=True, max_length=44),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='serie_nfe',
            field=models.CharField(blank=True, max_length=3),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='numero_nfe',
            field=models.CharField(
                blank=True,
                help_text='Número fiscal (nNF) — distinto do número interno.',
                max_length=9,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='codigo_numerico',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='digito_verificador',
            field=models.CharField(blank=True, max_length=1),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='numero_reservado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='numero_reservado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_entradas_numeracao_reservada',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='status_emissao_sefaz',
            field=models.CharField(
                blank=True,
                choices=[
                    ('NUMERACAO_RESERVADA', 'Numeração reservada'),
                    ('XML_GERADO', 'XML oficial gerado'),
                    ('XML_ASSINADO', 'XML assinado'),
                    ('ENVIADA_HOMOLOGACAO', 'Enviada homologação'),
                    ('AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'),
                    ('REJEITADA_HOMOLOGACAO', 'Rejeitada homologação'),
                    ('ERRO_TRANSMISSAO', 'Erro transmissão'),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_nfe_gerado',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_assinado',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_envio',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_retorno',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_autorizado',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_retorno_lote',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_protocolo',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_envio_lote',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='protocolo_autorizacao',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='autorizada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='cstat_autorizacao',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='motivo_autorizacao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='cstat_lote',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xmotivo_lote',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='recibo_lote',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='itemnfeentrada',
            name='numero_item',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemnfeentrada',
            name='ncm',
            field=models.CharField(blank=True, max_length=8),
        ),
        migrations.AddField(
            model_name='itemnfeentrada',
            name='cfop',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='itemnfeentrada',
            name='unidade',
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name='itemnfeentrada',
            name='descricao_xml',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='itemnfeentrada',
            name='impostos_json',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
