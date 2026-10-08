"""Campos separados lote vs NF-e e novos status de emissão SEFAZ."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0029_nfesaidaevento_emissao_homolog_iniciada'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaida',
            name='cstat_lote',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xmotivo_lote',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='recibo_lote',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_retorno_lote',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfesaida',
            name='xml_protocolo',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='nfesaida',
            name='cstat_autorizacao',
            field=models.CharField(
                blank=True,
                help_text='cStat final da NF-e (infProt), não do lote.',
                max_length=4,
            ),
        ),
        migrations.AlterField(
            model_name='nfesaida',
            name='motivo_autorizacao',
            field=models.TextField(
                blank=True,
                help_text='xMotivo final da NF-e (infProt), não do lote.',
            ),
        ),
        migrations.AlterField(
            model_name='nfesaida',
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
                    ('LOTE_PROCESSADO_SEM_PROTOCOLO', 'Lote processado sem protocolo'),
                    ('AGUARDANDO_PROCESSAMENTO', 'Aguardando processamento SEFAZ'),
                    ('ERRO_RETORNO_SEFAZ', 'Erro retorno SEFAZ'),
                ],
                max_length=32,
            ),
        ),
    ]
