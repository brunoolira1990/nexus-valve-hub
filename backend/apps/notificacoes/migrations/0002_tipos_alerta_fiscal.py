from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('notificacoes', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificacao',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('NOVO_LEAD', 'Novo lead'),
                    ('ATIVIDADE_VENCIDA', 'Atividade vencida'),
                    ('TITULO_VENCIDO', 'Título financeiro vencido'),
                    ('ESTOQUE_MINIMO', 'Estoque abaixo do mínimo'),
                    ('PROPOSTA_ACAO', 'Proposta aguardando ação'),
                    ('PENDENCIA_OPERACIONAL', 'Pendência operacional'),
                    ('DOCUMENTO_FISCAL', 'Documento fiscal'),
                    ('PENDENCIA_FISCAL', 'Pendência fiscal'),
                    ('FALHA_CAPTURA_FISCAL', 'Falha na captura fiscal'),
                    ('SISTEMA', 'Aviso do sistema'),
                ],
                db_index=True,
                default='SISTEMA',
                max_length=32,
            ),
        ),
    ]
