# Generated manually — evento CONSULTA_SITUACAO_SEFAZ

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0043_nfeentrada_nat_op_4015'),
    ]

    operations = [
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
                ],
                max_length=40,
            ),
        ),
    ]
