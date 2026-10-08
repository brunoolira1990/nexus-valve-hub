from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0075_nfeentrada_efeitos_devolucao_aplicados_em_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nfeentrada',
            name='status_operacional',
            field=models.CharField(
                choices=[
                    ('RASCUNHO', 'Rascunho'),
                    ('EM_CONFERENCIA', 'Em conferência'),
                    ('PRONTA_HOMOLOGACAO', 'Pronta homologação'),
                    ('AUTORIZADA_HOMOLOGACAO', 'Autorizada homologação'),
                    ('PRONTA_PRODUCAO', 'Pronta produção'),
                    ('AUTORIZADA_PRODUCAO', 'Autorizada produção'),
                    ('REJEITADA', 'Rejeitada'),
                    ('ERRO_TRANSMISSAO', 'Erro transmissão'),
                    ('INUTILIZADA_HOMOLOGACAO', 'Inutilizada homologação'),
                    ('INUTILIZADA_PRODUCAO', 'Inutilizada produção'),
                    ('CANCELADA_HOMOLOGACAO', 'Cancelada homologação'),
                    ('CANCELADA_PRODUCAO', 'Cancelada produção'),
                    ('IMPORTADA_PENDENTE_CONFERENCIA', 'Importada — pendente conferência'),
                ],
                default='RASCUNHO',
                max_length=40,
            ),
        ),
        migrations.AlterField(
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
                    ('ENVIADA_PRODUCAO', 'Enviada produção'),
                    ('AUTORIZADA_PRODUCAO', 'Autorizada produção'),
                    ('REJEITADA_PRODUCAO', 'Rejeitada produção'),
                    ('INUTILIZADA_HOMOLOGACAO', 'Inutilizada homologação'),
                    ('INUTILIZADA_PRODUCAO', 'Inutilizada produção'),
                    ('CANCELADA_HOMOLOGACAO', 'Cancelada homologação'),
                    ('CANCELADA_PRODUCAO', 'Cancelada produção'),
                    ('ERRO_TRANSMISSAO', 'Erro transmissão'),
                ],
                max_length=32,
            ),
        ),
    ]